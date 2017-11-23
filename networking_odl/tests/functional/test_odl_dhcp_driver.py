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

from neutron.tests.unit.plugins.ml2 import test_plugin
from neutron_lib import constants as n_const
from neutron_lib.plugins import directory
from oslo_config import fixture as config_fixture

from networking_odl.common import constants as odl_const
from networking_odl.dhcp import odl_dhcp_driver_base as driver_base
from networking_odl.tests.functional import base


class TestOdlDhcpDriver(base.V2DriverAdjustment, base.OdlTestsBase,
                        test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']

    def setUp(self):
        self.cfg = self.useFixture(config_fixture.Config())
        self.cfg.config(enable_dhcp_service=True, group='ml2_odl')
        super(TestOdlDhcpDriver, self).setUp()

    def get_port_data(self, network, subnet):
        plugin = self.get_plugin()
        device_id = driver_base.OPENDAYLIGHT_DEVICE_ID + \
            '-' + subnet[odl_const.ODL_SUBNET]['id']
        filters = {
            'network_id': [network[odl_const.ODL_NETWORK]['id']],
            'device_id': [device_id],
            'device_owner': [n_const.DEVICE_OWNER_DHCP]
        }
        ports = plugin.get_ports(self.context, filters=filters)
        if ports:
            port = ports[0]
            return {odl_const.ODL_PORT: {'id': port['id']}}

    def get_plugin(self):
        return directory.get_plugin()

    def test_subnet_create(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self.get_odl_resource(odl_const.ODL_SUBNET, subnet)
                port = self.get_port_data(network, subnet)
                self.assert_resource_created(odl_const.ODL_PORT, port)

    def test_subnet_update_from_disable_to_enable(self):
        with self.network() as network:
            with self.subnet(network=network, enable_dhcp=False) as subnet:
                self.get_odl_resource(odl_const.ODL_SUBNET, subnet)
                plugin = self.get_plugin()
                port = self.get_port_data(network, subnet)
                self.assertIsNone(port)
                subnet[odl_const.ODL_SUBNET]['enable_dhcp'] = True
                plugin.update_subnet(
                    self.context, subnet[odl_const.ODL_SUBNET]['id'], subnet)
                self.get_odl_resource(odl_const.ODL_SUBNET, subnet)
                port = self.get_port_data(network, subnet)
                self.assert_resource_created(odl_const.ODL_PORT, port)

    def test_subnet_update_from_enable_to_disable(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self.get_odl_resource(odl_const.ODL_SUBNET, subnet)
                plugin = self.get_plugin()
                port = self.get_port_data(network, subnet)
                self.assert_resource_created(odl_const.ODL_PORT, port)

                subnet[odl_const.ODL_SUBNET]['enable_dhcp'] = False
                plugin.update_subnet(
                    self.context, subnet[odl_const.ODL_SUBNET]['id'], subnet)
                resource = self.get_odl_resource(odl_const.ODL_PORT, port)
                self.assertIsNone(resource)

    def test_subnet_delete(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self.get_odl_resource(odl_const.ODL_SUBNET, subnet)
                plugin = self.get_plugin()
                port = self.get_port_data(network, subnet)
                self.assert_resource_created(odl_const.ODL_PORT, port)
                plugin.delete_subnet(
                    self.context, subnet[odl_const.ODL_SUBNET]['id'])
                resource = self.get_odl_resource(odl_const.ODL_PORT, port)
                self.assertIsNone(resource)
