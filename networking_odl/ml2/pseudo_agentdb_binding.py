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
from string import Template

from neutron_lib.api.definitions import portbindings
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib import constants as nl_const
from neutron_lib import context
from neutron_lib.plugins import directory
from neutron_lib.plugins.ml2 import api
from neutron_lib import worker
from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from requests import codes
from requests import exceptions

from neutron.db import provisioning_blocks

from networking_odl.common import client as odl_client
from networking_odl.common import odl_features
from networking_odl.common import utils
from networking_odl.common import websocket_client as odl_ws_client
from networking_odl.journal import periodic_task
from networking_odl.ml2 import port_binding

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = log.getLogger(__name__)


class PseudoAgentDBBindingTaskBase(object):
    def __init__(self, worker):
        super(PseudoAgentDBBindingTaskBase, self).__init__()
        self._worker = worker

        # extract host/port from ODL URL and append hostconf_uri path
        hostconf_uri = utils.get_odl_url(cfg.CONF.ml2_odl.odl_hostconf_uri)
        LOG.debug("ODLPORTBINDING hostconfigs URI: %s", hostconf_uri)

        # TODO(mzmalick): disable port-binding for ODL lightweight testing
        self.odl_rest_client = odl_client.OpenDaylightRestClient.create_client(
            url=hostconf_uri)

    def _rest_get_hostconfigs(self):
        try:
            response = self.odl_rest_client.get()
            response.raise_for_status()
            hostconfigs = response.json()['hostconfigs']['hostconfig']
        except exceptions.ConnectionError:
            LOG.error("Cannot connect to the OpenDaylight Controller",
                      exc_info=True)
            return None
        except exceptions.HTTPError as e:
            # restconf returns 404 on operation when there is no entry
            if e.response.status_code == codes.not_found:
                LOG.debug("Response code not_found (404)"
                          " treated as an empty list")
                return []

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

    def _get_and_update_hostconfigs(self, context=None):
        LOG.info("REST/GET hostconfigs from ODL")

        hostconfigs = self._rest_get_hostconfigs()

        if not hostconfigs:
            LOG.warning("ODL hostconfigs REST/GET failed, "
                        "will retry on next poll")
            return  # retry on next poll

        self._worker.update_agents_db(hostconfigs=hostconfigs)


@registry.has_registry_receivers
class PseudoAgentDBBindingPrePopulate(PseudoAgentDBBindingTaskBase):
    @registry.receives(resources.PORT,
                       [events.BEFORE_CREATE, events.BEFORE_UPDATE])
    def before_port_binding(self, resource, event, trigger, **kwargs):
        LOG.debug("before_port resource %s event %s %s",
                  resource, event, kwargs)
        assert resource == resources.PORT
        assert event in [events.BEFORE_CREATE, events.BEFORE_UPDATE]
        ml2_plugin = trigger
        context = kwargs['context']
        port = kwargs['port']

        host = nl_const.ATTR_NOT_SPECIFIED
        if port and portbindings.HOST_ID in port:
            host = port.get(portbindings.HOST_ID)
        if host == nl_const.ATTR_NOT_SPECIFIED or not host:
            return
        agent_type = PseudoAgentDBBindingWorker.L2_TYPE
        if self._worker.known_agent(host, agent_type):
            return
        agents = ml2_plugin.get_agents(
            context, filters={'agent_type': [agent_type], 'host': [host]})
        if agents and all(agent['alive'] for agent in agents):
            self._worker.add_known_agents(agents)
            LOG.debug("agents %s", agents)
            return

        # This host may not be created/updated by worker.
        # try to populate it.
        urlpath = "hostconfig/{0}/{1}".format(
            host, PseudoAgentDBBindingWorker.L2_TYPE)
        try:
            response = self.odl_rest_client.get(urlpath)
            response.raise_for_status()
        except Exception:
            LOG.warning("REST/GET odl hostconfig/%s failed.", host,
                        exc_info=True)
            return
        LOG.debug("response %s", response.json())
        hostconfig = response.json().get('hostconfig', [])
        if hostconfig:
            self._worker.update_agents_db_row(hostconfig[0])


class PseudoAgentDBBindingPeriodicTask(PseudoAgentDBBindingTaskBase):
    def __init__(self, worker):
        super(PseudoAgentDBBindingPeriodicTask, self).__init__(worker)

        # Start polling ODL restconf using maintenance thread.
        # default: 30s (should be <= agent keep-alive poll interval)
        self._periodic = periodic_task.PeriodicTask(
            'hostconfig', cfg.CONF.ml2_odl.restconf_poll_interval)
        self._periodic.register_operation(self._get_and_update_hostconfigs)
        self._periodic.start()


class PseudoAgentDBBindingWebSocket(PseudoAgentDBBindingTaskBase):
    def __init__(self, worker):
        super(PseudoAgentDBBindingWebSocket, self).__init__(worker)

        # Update hostconfig once for the configurations already present
        self._get_and_update_hostconfigs()
        odl_url = utils.get_odl_url()
        self._start_websocket(odl_url)

    def _start_websocket(self, odl_url):
        # OpenDaylight path to recieve websocket notifications on
        neutron_hostconfigs_path = """/neutron:neutron/neutron:hostconfigs"""

        self.odl_websocket_client = (
            odl_ws_client.OpenDaylightWebsocketClient.odl_create_websocket(
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
                    self._worker.delete_agents_db_row(
                        host_id.strip("'"), host_type.strip("'"))
                elif operation == event.OPERATION_CREATE:
                    if 'hostconfig' in data:
                        hostconfig = data['hostconfig']
                        self.update_agents_db_row(hostconfig)
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


class PseudoAgentDBBindingWorker(worker.BaseWorker):
    """Neutron Worker to update agentdb based on ODL hostconfig."""

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

    def __init__(self):
        LOG.info("PseudoAgentDBBindingWorker init")
        self._old_agents = set()
        self._known_agents = set()
        self.agents_db = None
        super(PseudoAgentDBBindingWorker, self).__init__()

    def start(self):
        LOG.info("PseudoAgentDBBindingWorker starting")
        super(PseudoAgentDBBindingWorker, self).start()
        self._start()

    def stop(self):
        pass

    def wait(self):
        pass

    def reset(self):
        pass

    def _start(self):
        """Initialization."""
        LOG.debug("Initializing ODL Port Binding Worker")
        if cfg.CONF.ml2_odl.enable_websocket_pseudo_agentdb:
            self._websocket = PseudoAgentDBBindingWebSocket(self)
        else:
            self._periodic_task = (PseudoAgentDBBindingPeriodicTask(self))

    def known_agent(self, host_id, agent_type):
        agent = (host_id, agent_type)
        return agent in self._known_agents or agent in self._old_agents

    def add_known_agents(self, agents):
        for agent in agents:
            self._known_agents.add((agent['host'], agent['agent_type']))

    def update_agents_db(self, hostconfigs):
        LOG.debug("ODLPORTBINDING Updating agents DB with ODL hostconfigs")

        self._old_agents = self._known_agents
        self._known_agents = set()
        for host_config in hostconfigs:
            self._update_agents_db_row(host_config)

    def update_agents_db_row(self, host_config):
        self._old_agents = self._known_agents
        self._update_agents_db_row(host_config)

    def _update_agents_db_row(self, host_config):
        if self.agents_db is None:
            self.agents_db = directory.get_plugin()

        # Update one row in agent db
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
            self.agents_db.create_or_update_agent(
                context.get_admin_context(), agentdb_row)
            self._known_agents.add((host_id, host_type))
        except Exception:
            LOG.exception("Unable to update agentdb.")

    def delete_agents_db_row(self, host_id, host_type):
        """Delete agent row."""
        try:
            filters = {'agent_type': [host_type],
                       'host': [host_id]}
            # TODO(rsood): get_agent can be used here
            agent = self.agents_db.get_agents_db(
                context.get_admin_context(), filters=filters)
            if not agent:
                return

            LOG.debug("Deleting Agent with Agent id: %s", agent[0]['id'])
            self.agents_db.delete_agent(
                context.get_admin_context(), agent[0]['id'])
            self._known_agents.remove((host_id, host_type))
        except Exception:
            LOG.exception("Unable to delete from agentdb.")


@registry.has_registry_receivers
class PseudoAgentDBBindingController(port_binding.PortBindingController):
    """Switch agnostic Port binding controller for OpenDayLight."""

    def __init__(self):
        """Initialization."""
        LOG.debug("Initializing ODL Port Binding Controller")
        super(PseudoAgentDBBindingController, self).__init__()
        self._worker = PseudoAgentDBBindingWorker()

    @registry.receives(resources.PROCESS, [events.BEFORE_SPAWN])
    def _before_spawn(self, resource, event, trigger, payload=None):
        self._prepopulate = PseudoAgentDBBindingPrePopulate(self._worker)

    def get_workers(self):
        return [self._worker]

    def _substitute_hconfig_tmpl(self, port_context, hconfig):
        # TODO(mzmalick): Explore options for inlines string splicing of
        #                 port-id to 14 bytes as required by vhostuser types
        port_id = port_context.current['id']
        conf = hconfig.get('configurations')
        vnics = conf.get('supported_vnic_types')
        if vnics is None:
            return hconfig
        for vnic in vnics:
            if vnic.get('vif_type') == portbindings.VIF_TYPE_VHOST_USER:
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
        agentdb = port_context.host_agents(PseudoAgentDBBindingWorker.L2_TYPE)

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
                    "Failed to bind Port %(pid)s devid %(device_id)s "
                    "owner %(owner)s for host %(host)s "
                    "on network %(network)s.", {
                        'pid': port_context.current['id'],
                        'device_id': port_context.current['device_id'],
                        'owner': port_context.current['device_owner'],
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

        vif_details = None
        for conf in confs:
            if conf["vnic_type"] == vnic_type:
                vif_type = conf.get('vif_type', portbindings.VIF_TYPE_OVS)
                LOG.debug("Binding vnic:'%s' to vif:'%s'", vnic_type, vif_type)
                vif_details = conf.get('vif_details', {})
                break
        else:
            LOG.error(
                "Binding failed: unsupported VNIC %(vnic_type)s on %(host)s",
                {'vnic_type': vnic_type, 'host': port_context.host})
            return False

        if not vif_details:  # empty vif_details could be trouble, warn.
            LOG.warning("hostconfig:vif_details was empty!")

        LOG.debug("Bind port %(port)s on network %(network)s with valid "
                  "segment %(segment)s and VIF type %(vif_type)r "
                  "VIF details %(vif_details)r.",
                  {'port': port_context.current['id'],
                   'network': port_context.network.current['id'],
                   'segment': valid_segment, 'vif_type': vif_type,
                   'vif_details': vif_details})

        port_status = self._prepare_initial_port_status(port_context)
        port_context.set_binding(valid_segment[api.ID], vif_type,
                                 vif_details, status=port_status)

        return True

    def _prepare_initial_port_status(self, port_context):
        port_status = nl_const.PORT_STATUS_ACTIVE
        if odl_features.has(odl_features.OPERATIONAL_PORT_STATUS):
            port_status = nl_const.PORT_STATUS_DOWN
            provisioning_blocks.add_provisioning_component(
                port_context._plugin_context, port_context.current['id'],
                resources.PORT, provisioning_blocks.L2_AGENT_ENTITY)
        return port_status

    def _is_valid_segment(self, segment, conf):
        """Verify a segment is supported by ODL."""
        network_type = segment[api.NETWORK_TYPE]
        return network_type in conf['allowed_network_types']
