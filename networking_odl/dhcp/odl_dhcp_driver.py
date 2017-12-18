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

from neutron_lib.callbacks import registry
from neutron_lib import constants as n_const
from neutron_lib.plugins import directory
from oslo_log import log as logging

from neutron.plugins.ml2 import driver_context

from networking_odl.common import constants
from networking_odl.dhcp import odl_dhcp_driver_base as driver_base


LOG = logging.getLogger(__name__)


@registry.has_registry_receivers
class OdlDhcpDriver(driver_base.OdlDhcpDriverBase):

    @registry.receives(constants.ODL_SUBNET, [constants.BEFORE_COMPLETE])
    def handle_subnet_event(self, resource, event, trigger, context=None,
                            operation=None, row=None, **kwargs):
        if (operation == constants.ODL_CREATE or
                operation == constants.ODL_UPDATE):
            try:
                subnet_ctxt = self._get_subnet_context(context,
                                                       row.data['network_id'],
                                                       row.data['id'])
                self.create_or_delete_dhcp_port(subnet_ctxt)
            except Exception as e:
                LOG.error("Error while processing %s subnet %s: %s", operation,
                          row.data['id'], e)

    @registry.receives(constants.ODL_PORT, [constants.BEFORE_COMPLETE])
    def handle_port_update_event(self, resource, event, trigger,
                                 context=None, operation=None,
                                 row=None, **kwargs):

        if operation == constants.ODL_UPDATE:
            try:
                self._delete_if_dhcp_port(context, row)
            except Exception as e:
                device_id = row.data['device_id']
                subnet_id = device_id[13:] if device_id else ''
                LOG.error("Error while processing %s port %s of subnet %s: %s",
                          operation, row.data['id'], subnet_id, e)

    def _get_subnet_context(self, context, network_id, subnet_id):
        plugin = directory.get_plugin()
        network = plugin.get_network(context, network_id)
        subnet = plugin.get_subnet(context, subnet_id)
        return driver_context.SubnetContext(plugin, context,
                                            subnet, network)

    def _delete_if_dhcp_port(self, context, row):

        device_owner = row.data['device_owner']
        device_id = row.data['device_id']
        fixed_ips = row.data['fixed_ips']
        device_id_type = driver_base.OPENDAYLIGHT_DEVICE_ID
        if (device_owner and device_owner == n_const.DEVICE_OWNER_DHCP and
                device_id and
                device_id.startswith(device_id_type) and not fixed_ips):
            plugin = directory.get_plugin()
            self._delete_port(plugin, context, row.data['id'])
