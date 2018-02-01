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
import testscenarios

from networking_odl.common import constants as odl_const
from networking_odl.dhcp import odl_dhcp_driver
from networking_odl.ml2 import mech_driver_v2
from networking_odl.tests.unit.dhcp import test_odl_dhcp_driver_base

from oslo_config import cfg

load_tests = testscenarios.load_tests_apply_scenarios

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')


class OdlDhcpDriverTestCase(test_odl_dhcp_driver_base.OdlDhcpDriverTestBase):

    def setUp(self):
        super(OdlDhcpDriverTestCase, self).setUp()
        self.cfg.config(enable_dhcp_service=True, group='ml2_odl')
        self.mech = mech_driver_v2.OpenDaylightMechanismDriver()
        self.mech.initialize()

    def test_dhcp_flag_test(self):
        self.assertTrue(cfg.CONF.ml2_odl.enable_dhcp_service)

    def test_dhcp_driver_load(self):
        self.assertTrue(isinstance(self.mech.dhcp_driver,
                                   odl_dhcp_driver.OdlDhcpDriver))

    def test_dhcp_port_create_on_subnet_event(self):

        data = self.get_network_and_subnet_context('10.0.50.0/24', True, True,
                                                   True)
        subnet_context = data['subnet_context']
        mech_driver_v2.OpenDaylightMechanismDriver._record_in_journal(
            subnet_context, odl_const.ODL_SUBNET, odl_const.ODL_CREATE)
        self.mech.journal.sync_pending_entries()

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNotNone(port)

    def test_dhcp_port_create_on_v6subnet_event(self):

        data = self.get_network_and_subnet_context('2001:db8:abcd:0012::0/64',
                                                   True, True, True, False)
        subnet_context = data['subnet_context']
        mech_driver_v2.OpenDaylightMechanismDriver._record_in_journal(
            subnet_context, odl_const.ODL_SUBNET, odl_const.ODL_CREATE)
        self.mech.journal.sync_pending_entries()

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNone(port)

    def test_dhcp_delete_on_port_update_event(self):

        data = self.get_network_and_subnet_context('10.0.50.0/24', True, True,
                                                   True)
        subnet_context = data['subnet_context']
        plugin = data['plugin']
        self.mech.dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        port_id = self.get_port_id(data['plugin'],
                                   data['context'],
                                   data['network_id'],
                                   data['subnet_id'])

        self.assertIsNotNone(port_id)

        port = plugin.get_port(data['context'], port_id)
        port['fixed_ips'] = []
        ports = {'port': port}
        plugin.update_port(data['context'], port_id, ports)

        mech_driver_v2.OpenDaylightMechanismDriver._record_in_journal(
            subnet_context, odl_const.ODL_PORT, odl_const.ODL_UPDATE, port)
        self.mech.journal.sync_pending_entries()
        port_id = self.get_port_id(data['plugin'],
                                   data['context'],
                                   data['network_id'],
                                   data['subnet_id'])
        self.assertIsNone(port_id)
