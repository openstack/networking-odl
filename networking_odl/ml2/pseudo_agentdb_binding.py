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

from neutron_lib.api.definitions import portbindings
from neutron_lib import constants as nl_const
from neutron_lib import context
from neutron_lib.plugins import directory
from neutron_lib.plugins.ml2 import api
from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from requests import codes
from requests import exceptions
import six.moves.urllib.parse as urlparse
from string import Template

from networking_odl.common import client as odl_client
from networking_odl.common import websocket_client as odl_ws_client
from networking_odl.journal import periodic_task as pt
from networking_odl.ml2 import port_binding

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = log.getLogger(__name__)


class PseudoAgentDBBindingController(port_binding.PortBindingController):
    """Switch agnostic Port binding controller for OpenDayLight."""

    AGENTDB_BINARY = 'neutron-odlagent-portbinding'
    L2_TYPE = "ODL L2"

    # TODO(mzmalick): binary, topic and resource_versions to be provided
    # by ODL, Pending ODL NB patches.
    _AGENTDB_ROW = {
        'binary': AGENTDB_BINARY,
        'host': '',
        'topic': nl_const.L2_AGENT_TOPIC,
        'configurations': {},
        'resource_versions': '',
        'agent_type': L2_TYPE,
        'start_flag': True}

    def __init__(self, hostconf_uri=None, db_plugin=None):
        """Initialization."""
        LOG.debug("Initializing ODL Port Binding Controller")

        if not hostconf_uri:
            # extract host/port from ODL URL and append hostconf_uri path
            hostconf_uri = self._make_hostconf_uri(
                cfg.CONF.ml2_odl.url, cfg.CONF.ml2_odl.odl_hostconf_uri)

        LOG.debug("ODLPORTBINDING hostconfigs URI: %s", hostconf_uri)

        # TODO(mzmalick): disable port-binding for ODL lightweight testing
        self.odl_rest_client = odl_client.OpenDaylightRestClient.create_client(
            url=hostconf_uri)

        # Neutron DB plugin instance
        self.agents_db = db_plugin
        self._known_agents = set()

        if cfg.CONF.ml2_odl.enable_websocket_pseudo_agentdb:
            # Update hostconfig once for the configurations already present
            self._get_and_update_hostconfigs()
            odl_url = self._make_odl_url(cfg.CONF.ml2_odl.url)
            self._start_websocket(odl_url)
        else:
            # Start polling ODL restconf using periodic task.
            # default: 30s (should be <=  agent keep-alive poll interval)
            self._start_periodic_task(
                cfg.CONF.ml2_odl.restconf_poll_interval)

    def _make_hostconf_uri(self, odl_url=None, path=''):
        """Make ODL hostconfigs URI with host/port extraced from ODL_URL."""
        # NOTE(yamahata): for unit test.
        odl_url = odl_url or 'http://localhost:8080/'

        # extract ODL_IP and ODL_PORT from ODL_ENDPOINT and append path
        # urlsplit and urlunparse don't throw exceptions
        purl = urlparse.urlsplit(odl_url)
        return urlparse.urlunparse((purl.scheme, purl.netloc,
                                    path, '', '', ''))

    def _make_odl_url(self, odl_url):
        """Extract host/port from ODL_URL to use for websocket."""

        # extract ODL_IP and ODL_PORT from ODL_ENDPOINT
        # urlsplit and urlunparse don't throw exceptions
        purl = urlparse.urlsplit(odl_url)
        return urlparse.urlunparse((purl.scheme, purl.netloc,
                                    '', '', '', ''))

    def _start_periodic_task(self, poll_interval):
        self._periodic = pt.PeriodicTask(poll_interval, 'hostconfig_update')
        self._periodic.register_operation(self._get_and_update_hostconfigs)
        self._periodic.start()

    def _rest_get_hostconfigs(self):
        try:
            response = self.odl_rest_client.get()
            response.raise_for_status()
            hostconfigs = response.json()['hostconfigs']['hostconfig']
        except exceptions.ConnectionError:
            LOG.error("Cannot connect to the Opendaylight Controller",
                      exc_info=True)
            return None
        except exceptions.HTTPError as e:
            # restconf returns 404 on operation when there is no entry
            if e.response.status_code == codes.not_found:
                LOG.debug("Response code not_found (404)"
                          " treated as an empty list")
                return []
            else:
                LOG.warning("REST/GET odl hostconfig failed, ",
                            exc_info=True)
                return None
        except KeyError:
            LOG.error("got invalid hostconfigs", exc_info=True)
            return None
        except Exception:
            LOG.warning("REST/GET odl hostconfig failed, ",
                        exc_info=True)
            return None
        else:
            if LOG.isEnabledFor(logging.DEBUG):
                _hconfig_str = jsonutils.dumps(
                    response, sort_keys=True, indent=4, separators=(',', ': '))
                LOG.debug("ODLPORTBINDING hostconfigs:\n%s", _hconfig_str)

        return hostconfigs

    def _get_and_update_hostconfigs(self, session=None):
        LOG.info("REST/GET hostconfigs from ODL")

        hostconfigs = self._rest_get_hostconfigs()

        if not hostconfigs:
            LOG.warning("ODL hostconfigs REST/GET failed, "
                        "will retry on next poll")
            return  # retry on next poll

        self._update_agents_db(hostconfigs=hostconfigs)

    def _get_neutron_db_plugin(self):
        if not self.agents_db:
            self.agents_db = directory.get_plugin()
        return self.agents_db

    def _update_agents_db(self, hostconfigs):
        LOG.debug("ODLPORTBINDING Updating agents DB with ODL hostconfigs")

        self._old_agents = self._known_agents
        self._known_agents = set()
        for host_config in hostconfigs:
            self._update_agents_db_row(host_config)

    def _update_agents_db_row(self, host_config):
        # Update one row in agent db
        agents_db = self._get_neutron_db_plugin()
        if not agents_db:  # if ML2 is still initializing
            LOG.error("ML2 still initializing, Missed an update")
            # TODO(rsood): Neutron worker can be used
            return
        host_id = host_config['host-id']
        host_type = host_config['host-type']
        config = host_config['config']
        try:
            agentdb_row = self._AGENTDB_ROW.copy()
            agentdb_row['host'] = host_id
            agentdb_row['agent_type'] = host_type
            agentdb_row['configurations'] = jsonutils.loads(config)
            if (host_id, host_type) in self._old_agents:
                agentdb_row.pop('start_flag', None)
            agents_db.create_or_update_agent(
                context.get_admin_context(), agentdb_row)
            self._known_agents.add((host_id, host_type))
        except Exception:
            LOG.exception("Unable to update agentdb.")

    def _delete_agents_db_row(self, host_id, host_type):
        """Delete agent row."""
        agents_db = self._get_neutron_db_plugin()
        if not agents_db:  # if ML2 is still initializing
            LOG.error("ML2 still initializing, Missed an update")
            return None
        try:
            filters = {'agent_type': [host_type],
                       'host': [host_id]}
            # TODO(rsood): get_agent can be used here
            agent = agents_db.get_agents_db(
                context.get_admin_context(), filters=filters)
            if not agent:
                return

            LOG.debug("Deleting Agent with Agent id: %s", agent[0]['id'])
            agents_db.delete_agent(context.get_admin_context(), agent[0]['id'])
            self._known_agents.remove((host_id, host_type))
        except Exception:
            LOG.exception("Unable to delete from agentdb.")

    def _substitute_hconfig_tmpl(self, port_context, hconfig):
        # TODO(mzmalick): Explore options for inlines string splicing of
        #                 port-id to 14 bytes as required by vhostuser types
        port_id = port_context.current['id']
        conf = hconfig.get('configurations')
        vnics = conf.get('supported_vnic_types')
        if vnics is None:
            return hconfig
        for vnic in vnics:
            if vnic.get('vif_type') is portbindings.VIF_TYPE_VHOST_USER:
                details = vnic.get('vif_details')
                if details is None:
                    continue
                port_prefix = details.get('port_prefix')
                port_prefix = port_prefix[:14]
                subs_ids = {
                    # $IDENTIFER string substitution in hostconfigs JSON string
                    'PORT_ID': port_id[:(14 - len(port_prefix))],
                }
                # Substitute identifiers and Convert JSON string to dict
                hconfig_conf_json = Template(jsonutils.dumps(details))
                substituted_str = hconfig_conf_json.safe_substitute(subs_ids)
                vnic['vif_details'] = jsonutils.loads(substituted_str)
        return hconfig

    def bind_port(self, port_context):
        """bind port using ODL host configuration."""
        # Get all ODL hostconfigs for this host and type
        agentdb = port_context.host_agents(self.L2_TYPE)

        if not agentdb:
            LOG.warning("No valid hostconfigs in agentsdb for host %s",
                        port_context.host)
            return

        for raw_hconfig in agentdb:
            # do any $identifier substitution
            hconfig = self._substitute_hconfig_tmpl(port_context, raw_hconfig)

            # Found ODL hostconfig for this host in agentdb
            LOG.debug("ODLPORTBINDING bind port with hostconfig: %s", hconfig)

            if self._hconfig_bind_port(port_context, hconfig):
                break  # Port binding suceeded!
            else:  # Port binding failed!
                LOG.warning(
                    "Failed to bind Port %(pid)s for host %(host)s on network "
                    "%(network)s.", {
                        'pid': port_context.current['id'],
                        'host': port_context.host,
                        'network': port_context.network.current['id']})
        else:  # No hostconfig found for host in agentdb.
            LOG.warning("No ODL hostconfigs for host %s found in agentdb",
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
            LOG.error("Binding failed: unsupported VNIC %s", vnic_type)
            return False

        for conf in confs:
            if conf["vnic_type"] == vnic_type:
                vif_type = conf.get('vif_type', portbindings.VIF_TYPE_OVS)
                LOG.debug("Binding vnic:'%s' to vif:'%s'", vnic_type, vif_type)
                break
        else:
            vif_type = portbindings.VIF_TYPE_OVS  # default: OVS
            LOG.warning("No supported vif type found for host %s!, "
                        "defaulting to OVS", port_context.host)

        vif_details = conf.get('vif_details', {})

        if not vif_details:  # empty vif_details could be trouble, warn.
            LOG.warning("hostconfig:vif_details was empty!")

        LOG.debug("Bind port %(port)s on network %(network)s with valid "
                  "segment %(segment)s and VIF type %(vif_type)r "
                  "VIF details %(vif_details)r.",
                  {'port': port_context.current['id'],
                   'network': port_context.network.current['id'],
                   'segment': valid_segment, 'vif_type': vif_type,
                   'vif_details': vif_details})

        port_context.set_binding(valid_segment[api.ID], vif_type,
                                 vif_details,
                                 status=nl_const.PORT_STATUS_ACTIVE)
        return True

    def _is_valid_segment(self, segment, conf):
        """Verify a segment is supported by ODL."""
        network_type = segment[api.NETWORK_TYPE]
        return network_type in conf['allowed_network_types']

    def _start_websocket(self, odl_url):
        # Opendaylight path to recieve websocket notifications on
        neutron_hostconfigs_path = """/neutron:neutron/neutron:hostconfigs"""

        self.odl_websocket_client = (
            odl_ws_client.OpendaylightWebsocketClient.odl_create_websocket(
                odl_url, neutron_hostconfigs_path,
                odl_ws_client.ODL_OPERATIONAL_DATASTORE,
                odl_ws_client.ODL_NOTIFICATION_SCOPE_SUBTREE,
                self._process_websocket_recv,
                self._process_websocket_reconnect
            ))
        if self.odl_websocket_client is None:
            LOG.error("Error starting websocket thread")

    def _process_websocket_recv(self, payload, reconnect):
        # Callback for websocket notification
        LOG.debug("Websocket notification for hostconfig update")
        for event in odl_ws_client.EventDataParser.get_item(payload):
            try:
                operation, path, data = event.get_fields()
                if operation == event.OPERATION_DELETE:
                    host_id = event.extract_field(path, "neutron:host-id")
                    host_type = event.extract_field(path, "neutron:host-type")
                    if not host_id or not host_type:
                        LOG.warning("Invalid delete notification")
                        continue
                    self._delete_agents_db_row(host_id.strip("'"),
                                               host_type.strip("'"))
                elif operation == event.OPERATION_CREATE:
                    if 'hostconfig' in data:
                        hostconfig = data['hostconfig']
                        self._old_agents = self._known_agents
                        self._update_agents_db_row(hostconfig)
            except KeyError:
                LOG.warning("Invalid JSON for websocket notification",
                            exc_info=True)
                continue

    # TODO(rsood): Mixing restconf and websocket can cause race conditions
    def _process_websocket_reconnect(self, status):
        if status == odl_ws_client.ODL_WEBSOCKET_CONNECTED:
            # Get hostconfig data using restconf
            LOG.debug("Websocket notification on reconnection")
            self._get_and_update_hostconfigs()
