#
# Copyright (C) 2013 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#

from oslo_config import cfg
from oslo_log import log as logging

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron.api.rpc.handlers import l3_rpc
from neutron.common import constants as q_const
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron.db import extraroute_db
from neutron.db import l3_agentschedulers_db
from neutron.db import l3_dvr_db
from neutron.db import l3_gwmode_db
from neutron.plugins.common import constants

from networking_odl.common import client as odl_client
from networking_odl.common import utils as odl_utils

try:
    from neutron.db.db_base_plugin_v2 import common_db_mixin
except ImportError as e:
    # the change set ofece8cc2e9aae1610a325d0c206e38da3da9a0a1a
    # the Change-Id of I1eac61c258541bca80e14be4b7c75519a014ffae
    # db_base_plugin_v2.common_db_mixin was removed
    from neutron.db import common_db_mixin


cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = logging.getLogger(__name__)
ROUTERS = 'routers'
FLOATINGIPS = 'floatingips'


class OpenDaylightL3RouterPlugin(
    common_db_mixin.CommonDbMixin,
    extraroute_db.ExtraRoute_db_mixin,
    l3_dvr_db.L3_NAT_with_dvr_db_mixin,
    l3_gwmode_db.L3_NAT_db_mixin,
    l3_agentschedulers_db.L3AgentSchedulerDbMixin):

    """Implementation of the OpenDaylight L3 Router Service Plugin.

    This class implements a L3 service plugin that provides
    router and floatingip resources and manages associated
    request/response.
    """
    supported_extension_aliases = ["dvr", "router", "ext-gw-mode",
                                   "extraroute"]

    def __init__(self):
        self.setup_rpc()
        self.client = odl_client.OpenDaylightRestClient.create_client()

    def setup_rpc(self):
        self.topic = topics.L3PLUGIN
        self.conn = n_rpc.create_connection()
        self.agent_notifiers.update(
            {q_const.AGENT_TYPE_L3: l3_rpc_agent_api.L3AgentNotifyAPI()})
        self.endpoints = [l3_rpc.L3RpcCallback()]
        self.conn.create_consumer(self.topic, self.endpoints,
                                  fanout=False)
        self.conn.consume_in_threads()

    def get_plugin_type(self):
        return constants.L3_ROUTER_NAT

    def get_plugin_description(self):
        """returns string description of the plugin."""
        return ("L3 Router Service Plugin for basic L3 forwarding"
                " using OpenDaylight")

    def filter_update_router_attributes(self, router):
        """Filter out router attributes for an update operation."""
        odl_utils.try_del(router, ['id', 'tenant_id', 'status'])

    def create_router(self, context, router):
        router_dict = super(OpenDaylightL3RouterPlugin, self).create_router(
            context, router)
        url = ROUTERS
        self.client.sendjson('post', url, {ROUTERS[:-1]: router_dict})
        return router_dict

    def update_router(self, context, id, router):
        router_dict = super(OpenDaylightL3RouterPlugin, self).update_router(
            context, id, router)
        url = ROUTERS + "/" + id
        resource = router_dict.copy()
        self.filter_update_router_attributes(resource)
        self.client.sendjson('put', url, {ROUTERS[:-1]: resource})
        return router_dict

    def delete_router(self, context, id):
        super(OpenDaylightL3RouterPlugin, self).delete_router(context, id)
        url = ROUTERS + "/" + id
        self.client.sendjson('delete', url, None)

    def create_floatingip(self, context, floatingip,
                          initial_status=q_const.FLOATINGIP_STATUS_ACTIVE):
        fip_dict = super(OpenDaylightL3RouterPlugin, self).create_floatingip(
            context, floatingip, initial_status)
        url = FLOATINGIPS
        self.client.sendjson('post', url, {FLOATINGIPS[:-1]: fip_dict})
        return fip_dict

    def update_floatingip(self, context, id, floatingip):
        with context.session.begin(subtransactions=True):
            fip_dict = super(OpenDaylightL3RouterPlugin,
                             self).update_floatingip(context, id, floatingip)
            # Update status based on association
            if fip_dict.get('port_id') is None:
                fip_dict['status'] = q_const.FLOATINGIP_STATUS_DOWN
            else:
                fip_dict['status'] = q_const.FLOATINGIP_STATUS_ACTIVE
            self.update_floatingip_status(context, id, fip_dict['status'])

        url = FLOATINGIPS + "/" + id
        self.client.sendjson('put', url, {FLOATINGIPS[:-1]: fip_dict})
        return fip_dict

    def delete_floatingip(self, context, id):
        super(OpenDaylightL3RouterPlugin, self).delete_floatingip(context, id)
        url = FLOATINGIPS + "/" + id
        self.client.sendjson('delete', url, None)

    def add_router_interface(self, context, router_id, interface_info):
        new_router = super(
            OpenDaylightL3RouterPlugin, self).add_router_interface(
                context, router_id, interface_info)
        url = ROUTERS + "/" + router_id + "/add_router_interface"
        router_dict = self._generate_router_dict(router_id, interface_info,
                                                 new_router)
        self.client.sendjson('put', url, router_dict)
        return new_router

    def remove_router_interface(self, context, router_id, interface_info):
        new_router = super(
            OpenDaylightL3RouterPlugin, self).remove_router_interface(
                context, router_id, interface_info)
        url = ROUTERS + "/" + router_id + "/remove_router_interface"
        router_dict = self._generate_router_dict(router_id, interface_info,
                                                 new_router)
        self.client.sendjson('put', url, router_dict)
        return new_router

    def _generate_router_dict(self, router_id, interface_info, new_router):
        # Get network info for the subnet that is being added to the router.
        # Check if the interface information is by port-id or subnet-id
        add_by_port, add_by_sub = self._validate_interface_info(interface_info)
        if add_by_sub:
            _port_id = new_router['port_id']
            _subnet_id = interface_info['subnet_id']
        elif add_by_port:
            _port_id = interface_info['port_id']
            _subnet_id = new_router['subnet_id']

        router_dict = {'subnet_id': _subnet_id,
                       'port_id': _port_id,
                       'id': router_id,
                       'tenant_id': new_router['tenant_id']}

        return router_dict

    dvr_deletens_if_no_port_warned = False

    def dvr_deletens_if_no_port(self, context, port_id):
        # TODO(yamahata): implement this method or delete this logging
        # For now, this is defined to avoid attribute exception
        # Since ODL L3 does not create namespaces, this is always going to
        # be a noop. When it is confirmed, delete this comment and logging
        if not self.dvr_deletens_if_no_port_warned:
            LOG.debug('dvr is not suported yet. '
                      'this method needs to be implemented')
            self.dvr_deletens_if_no_port_warned = True
        return []
