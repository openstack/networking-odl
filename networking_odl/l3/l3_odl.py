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

from oslo.config import cfg

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron.common import constants as q_const
from neutron.common import rpc as n_rpc
from neutron.common import topics
import neutron.db as db
from neutron.plugins.common import constants

from networking_odl.common import client as odl_client
from networking_odl.common import config  # noqa
from networking_odl.common import utils as odl_utils

ROUTERS = 'routers'
FLOATINGIPS = 'floatingips'


class OpenDaylightRouterPluginRpcCallbacks(n_rpc.RpcCallback,
                                           db.l3_rpc_base.L3RpcCallbackMixin):
    RPC_API_VERSION = '1.3'


class OpenDaylightL3RouterPlugin(db.common_db_mixin.CommonDbMixin,
                                 db.extraroute_db.ExtraRoute_db_mixin,
                                 db.l3_dvr_db.L3_NAT_with_dvr_db_mixin,
                                 db.l3_gwmode_db.L3_NAT_db_mixin):

    """Implementation of the OpenDaylight L3 Router Service Plugin.

    This class implements a L3 service plugin that provides
    router and floatingip resources and manages associated
    request/response.
    """
    supported_extension_aliases = ["dvr", "router", "ext-gw-mode",
                                   "extraroute"]

    def __init__(self):
        self.setup_rpc()
        self.client = odl_client.OpenDaylightRestClient(
            cfg.CONF.odl_rest.url,
            cfg.CONF.odl_rest.username,
            cfg.CONF.odl_rest.password,
            cfg.CONF.odl_rest.timeout,
            cfg.CONF.odl_rest.session_timeout
        )

    def setup_rpc(self):
        self.topic = topics.L3PLUGIN
        self.conn = n_rpc.create_connection(new=True)
        self.agent_notifiers.update(
            {q_const.AGENT_TYPE_L3: l3_rpc_agent_api.L3AgentNotifyAPI()})
        self.endpoints = [OpenDaylightRouterPluginRpcCallbacks()]
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
        super(OpenDaylightL3RouterPlugin, self).update_router(context, id)
        url = ROUTERS + "/" + id
        self.client.sendjson('delete', url, None)

    def create_floatingip(self, context, floatingip,
                          initial_status=q_const.FLOATINGIP_STATUS_ACTIVE):
        fip_dict = super(OpenDaylightL3RouterPlugin, self).create_floatingip(
            context, floatingip)
        url = FLOATINGIPS
        self.client.sendjson('post', url, {FLOATINGIPS[:-1]: fip_dict})
        return fip_dict

    def update_floatingip(self, context, id, floatingip):
        fip_dict = super(OpenDaylightL3RouterPlugin, self).update_floatingip(
            context, id, floatingip)
        url = FLOATINGIPS + "/" + id
        self.client.sendjson('put', url, {FLOATINGIPS[:-1]: fip_dict})
        return fip_dict

    def delete_floatingip(self, context, id):
        super(OpenDaylightL3RouterPlugin, self).update_floatingip(context, id)
        url = FLOATINGIPS + "/" + id
        self.client.sendjson('delete', url, None)
