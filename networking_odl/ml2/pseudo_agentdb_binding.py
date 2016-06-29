# Copyright (c) 2016 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
from neutron_lib import constants as nl_const
from requests import exceptions
import six.moves.urllib.parse as urlparse

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils

from neutron.common import constants as n_const
from neutron import context
from neutron.extensions import portbindings
from neutron import manager
from neutron.plugins.ml2 import driver_api

from networking_odl._i18n import _LE, _LI, _LW
from networking_odl.common import client as odl_client
from networking_odl.journal import maintenance as mt
from networking_odl.ml2 import port_binding

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = log.getLogger(__name__)

AGENTDB_BINARY = 'neutron-odlagent-portbinding'
L2_TYPE = "ODL L2"


class PseudoAgentDBBindingController(port_binding.PortBindingController):
    """Switch agnostic Port binding controller for OpenDayLight."""

    def __init__(self, hostconf_uri=None, agent_db=None):
        """Initialization."""
        LOG.debug("Initializing ODL Port Binding Controller")

        if not hostconf_uri:
            # extract host/port from ODL URL and append hostconf_uri path
            hostconf_uri = self._make_hostconf_uri(
                cfg.CONF.ml2_odl.url, cfg.CONF.ml2_odl.odl_hostconf_uri)

        LOG.debug("ODLPORTBINDING hostconfigs URI: %s", hostconf_uri)

        self.agent_db = agent_db

        # TODO(mzmalick): disable port-binding for ODL lightweight testing
        self.odl_rest_client = odl_client.OpenDaylightRestClient.create_client(
            url=hostconf_uri)

        # Start polling ODL restconf using maintenance thread.
        # default: 30s (should be <=  agent keep-alive poll interval)
        self._start_maintenance_thread(cfg.CONF.ml2_odl.restconf_poll_interval)

    def _make_hostconf_uri(self, odl_url='http://localhost:8080/', path=''):
        """Make ODL hostconfigs URI with host/port extraced from ODL_URL."""
        # extract ODL_IP and ODL_PORT from ODL_ENDPOINT and append path
        # urlsplit and urlunparse don't throw exceptions
        purl = urlparse.urlsplit(odl_url)
        return urlparse.urlunparse((purl.scheme, purl.netloc,
                                    path, '', '', ''))
    #
    # TODO(mzmalick):
    # 1. implement websockets for ODL hostconfig events
    #

    def _start_maintenance_thread(self, poll_interval):
        self._mainth = mt.MaintenanceThread()
        self._mainth.maintenance_interval = poll_interval
        self._mainth.register_operation(self._get_and_update_hostconfigs)
        self._mainth.start()

    def _get_and_update_hostconfigs(self, session=None):
        LOG.info(_LI("REST/GET hostconfigs from ODL"))

        if not self.agent_db:
            if manager.NeutronManager.has_instance():
                self.agent_db = manager.NeutronManager.get_plugin()
            else:
                LOG.warning(_LW("ML2 still initializing, Will retry agentdb"
                                " update on next poll"))
                return  # Retry on next poll if ML2 still init'ing

        try:
            response = self.odl_rest_client.get()
            response.raise_for_status()

            host_configs = response.json()['hostconfigs']['hostconfig']

            if not host_configs:
                LOG.warning(_LE("hostconfigs not fetched yet, "
                                "retry on next poll"))
                return
        except exceptions.ConnectionError:
            LOG.error(_LE("Cannot connect to the Opendaylight Controller"
                          "will retry again"))
            return  # retry on next poll
        except Exception:
            LOG.warning(_LW("rest/get odl hostconfig failed, "
                            "will retry again"), exc_info=1)
            return  # retry on next poll
        else:
            if LOG.isEnabledFor(logging.DEBUG):
                _hconfig_str = jsonutils.dumps(host_configs, sort_keys=True,
                                               indent=4,
                                               separators=(',', ': '))
                LOG.debug("ODLPORTBINDING hostconfigs:\n%s", _hconfig_str)
            self._update_agents_db(self.agent_db, host_configs)

    def _update_agents_db(self, agent_db, host_configs):
        LOG.debug("ODLPORTBINDING Updating agents DB with ODL hostconfigs")

        # TODO(mzmalick): binary, topic and resource_versions to be provided
        # by ODL, Pending ODL NB patches.
        agentdb_row = {
            'binary': AGENTDB_BINARY,
            'host': '',
            'topic': nl_const.L2_AGENT_TOPIC,
            'configurations': {},
            'resource_versions': '',
            'agent_type': L2_TYPE,
            'start_flag': True}
        # We are not running host agents, so above start_flag is redundant

        for host_config in host_configs:
            try:
                agentdb_row['host'] = host_config['host-id']
                agentdb_row['agent_type'] = host_config['host-type']

                # ODL returns config as a json string, convert to dict
                agentdb_row['configurations'] = jsonutils.loads(
                    host_config['config'])

                agent_db.create_or_update_agent(context.get_admin_context(),
                                                agentdb_row)
            except Exception:
                LOG.exception(_LE("Unable to update agentdb."))
                continue  # try next hostcofig

    def bind_port(self, port_context):
        """bind port using ODL host configuration."""
        # Get all ODL hostconfigs for this host and type
        agentdb = port_context.host_agents(L2_TYPE)

        if not agentdb:
            LOG.warning(_LW("No valid hostconfigs in agentsdb for host %s"),
                        port_context.host)
            return

        for hconfig in agentdb:
            # Found ODL hostconfig for this host in agentdb
            LOG.debug("ODLPORTBINDING bind port with hostconfig: %s", hconfig)
            if self._hconfig_bind_port(port_context, hconfig):
                break  # Port binding suceeded!
            else:  # Port binding failed!
                LOG.warning(_LW("Failed to bind Port %(pid)s for host "
                            "%(host)s on network %(network)s."), {
                    'pid': port_context.current['id'],
                    'host': port_context.host,
                    'network': port_context.network.current['id']})
        else:  # No hostconfig found for host in agentdb.
            LOG.warning(_LW("No ODL hostconfigs for host %s found in agentdb"),
                        port_context.host)

    def _hconfig_bind_port(self, port_context, hconfig):
        """bind port after validating odl host configuration."""
        valid_segment = None

        for segment in port_context.segments_to_bind:
            if self._is_valid_segment(segment, hconfig['configurations']):
                valid_segment = segment
                break
        else:
            LOG.debug("No valid segments found!")
            return False

        confs = hconfig['configurations']['supported_vnic_types']

        # nova provides vnic_type in port_context to neutron.
        # neutron provides supported vif_type for binding based on vnic_type
        # in this case ODL hostconfigs has the vif_type to bind for vnic_type
        vnic_type = port_context.current.get(portbindings.VNIC_TYPE)

        if vnic_type != portbindings.VNIC_NORMAL:
            LOG.error(_LE("Binding failed: unsupported VNIC %s"), vnic_type)
            return False

        for conf in confs:
            if conf["vnic_type"] == vnic_type:
                vif_type = conf.get('vif_type', portbindings.VIF_TYPE_OVS)
                LOG.debug("Binding vnic:'%s' to vif:'%s'", vnic_type, vif_type)
                break
        else:
            vif_type = portbindings.VIF_TYPE_OVS  # default: OVS
            LOG.warning(_LW("No supported vif type found for host %s!, "
                            "defaulting to OVS"), port_context.host)

        vif_details = conf.get('vif_details', {})

        if not vif_details:  # empty vif_details could be trouble, warn.
            LOG.warning(_LW("hostconfig:vif_details was empty!"))

        LOG.debug("Bind port %(port)s on network %(network)s with valid "
                  "segment %(segment)s and VIF type %(vif_type)r "
                  "VIF details %(vif_details)r.",
                  {'port': port_context.current['id'],
                   'network': port_context.network.current['id'],
                   'segment': valid_segment, 'vif_type': vif_type,
                   'vif_details': vif_details})

        port_context.set_binding(valid_segment[driver_api.ID], vif_type,
                                 vif_details,
                                 status=n_const.PORT_STATUS_ACTIVE)
        return True

    def _is_valid_segment(self, segment, conf):
        """Verify a segment is supported by ODL."""
        network_type = segment[driver_api.NETWORK_TYPE]
        return network_type in conf['allowed_network_types']
