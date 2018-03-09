# Copyright (c) 2017 OpenStack Foundation
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


from neutron_lib import constants as n_const
from oslo_log import log as logging

from neutron.db import api as db_api
from neutron.plugins.common import utils as p_utils


LOG = logging.getLogger(__name__)
OPENDAYLIGHT_DEVICE_ID = 'OpenDaylight'


class OdlDhcpDriverBase(object):

    # NOTE:(Karthik Prasad/karthik.prasad) Not validating based on value change
    # of enable_dhcp in case of subnet update event, instead validating on
    # port_id presence in DB by locking the session, this will enable user to
    # reissue the same command in case of failure.
    @db_api.retry_db_errors
    def create_or_delete_dhcp_port(self, subnet_context):
        # NOTE:(Achuth) Fixes bug 1746715
        # DHCP port to be created for IPv4 subnets only, since ODL doesn't
        # support IPv6 neutron port ARP responses. This prevents validations
        # in ODL and avoids processing  these ports incorrectly.
        if subnet_context.current['ip_version'] != 4:
            LOG.warning("ODL DHCP port is supported  only for IPv4 subnet %s",
                        subnet_context.current['id'])
            return
        port_id = self.get_dhcp_port_if_exists(subnet_context)
        plugin = subnet_context._plugin
        if not port_id and subnet_context.current['enable_dhcp']:
            LOG.debug("Creating ODL DHCP port for subnet %s of network %s",
                      subnet_context.current['id'],
                      subnet_context.current['network_id'])
            port = self._make_dhcp_port_dict(subnet_context)
            p_utils.create_port(plugin, subnet_context._plugin_context, port)
        if port_id and not subnet_context.current['enable_dhcp']:
            self._delete_port(plugin, subnet_context._plugin_context, port_id)

    @db_api.retry_db_errors
    def _delete_port(self, plugin, context, port_id):
        LOG.debug("Deleting ODL DHCP port with id %s", port_id)
        plugin.delete_port(context, port_id)

    def _make_dhcp_port_dict(self, subnet_context):

        subnet_id = subnet_context.current['id']
        port_dict = dict(
            name='',
            admin_state_up=True,
            device_id=OPENDAYLIGHT_DEVICE_ID + '-' + subnet_id,
            device_owner=n_const.DEVICE_OWNER_DHCP,
            network_id=subnet_context.current['network_id'],
            fixed_ips=[dict(subnet_id=subnet_id)],
            tenant_id=subnet_context.network.current['tenant_id'])

        return {'port': port_dict}

    @db_api.retry_db_errors
    def get_dhcp_port_if_exists(self, subnet_context):

        plugin = subnet_context._plugin
        plugin_context = subnet_context._plugin_context
        network_id = subnet_context._subnet['network_id']
        subnet_id = subnet_context.current['id']
        device_id = OPENDAYLIGHT_DEVICE_ID + '-' + subnet_id
        LOG.debug("Retrieving ODL DHCP port for subnet %s", subnet_id)
        filters = {
            'network_id': [network_id],
            'device_id': [device_id],
            'device_owner': [n_const.DEVICE_OWNER_DHCP]
        }
        ports = plugin.get_ports(plugin_context, filters=filters)
        if ports:
            port = ports[0]
            LOG.debug("Retrieved ODL owned port %s for subnet %s",
                      port['id'], subnet_id)
            return port['id']
        return None
