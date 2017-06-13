# Copyright (c) 2017 Ericsson India Global Service Pvt Ltd.
# All Rights Reserved.
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


import contextlib

from networking_odl.common import constants as odl_const
from networking_odl.tests.functional import base
from neutron.plugins.common import utils
from neutron.services.trunk import constants
from neutron.services.trunk import plugin as trunk_plugin
from neutron.tests.unit.plugins.ml2 import test_plugin

from oslo_utils import uuidutils


class _TrunkDriverTest(base.OdlTestsBase):

    def test_trunk_create(self):
        with self.trunk() as trunk:
            self.assert_resource_created(odl_const.ODL_TRUNK, trunk)

    def test_trunk_update(self):
        with self.trunk() as trunk:
            trunk['trunk'].update(admin_state_up=False)
            self.trunk_plugin.update_trunk(self.context,
                                           trunk['trunk']['id'], trunk)
            response = self.get_odl_resource(odl_const.ODL_TRUNK, trunk)
            self.assertFalse(response['trunk']['admin_state_up'])

    def test_subport_create(self):
        with self.trunk() as trunk:
            with self.subport() as subport:
                trunk_obj = self.trunk_plugin.add_subports(
                    self.context, trunk['trunk']['id'],
                    {'sub_ports': [subport]})
                response = self.get_odl_resource(odl_const.ODL_TRUNK,
                                                 {'trunk': trunk_obj})
                self.assertEqual(response['trunk']['sub_ports'][0]['port_id'],
                                 subport['port_id'])

    def test_subport_delete(self):
        with self.subport() as subport:
            with self.trunk([subport]) as trunk:
                response = self.get_odl_resource(odl_const.ODL_TRUNK, trunk)
                self.assertEqual(response['trunk']['sub_ports'][0]['port_id'],
                                 subport['port_id'])
                trunk_obj = self.trunk_plugin.remove_subports(
                    self.context, trunk['trunk']['id'],
                    {'sub_ports': [subport]})
                response = self.get_odl_resource(odl_const.ODL_TRUNK,
                                                 {'trunk': trunk_obj})
                self.assertEqual(response['trunk']['sub_ports'], [])

    def test_trunk_delete(self):
        with self.trunk() as trunk:
            self.trunk_plugin.delete_trunk(self.context, trunk['trunk']['id'])
            self.assertIsNone(self.get_odl_resource(odl_const.ODL_TRUNK,
                                                    trunk))

    @contextlib.contextmanager
    def trunk(self, subports=None):
        subports = subports if subports else []
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                with self.port(subnet=subnet) as trunk_parent:
                    tenant_id = uuidutils.generate_uuid()
                    trunk = {'port_id': trunk_parent['port']['id'],
                             'tenant_id': tenant_id, 'project_id': tenant_id,
                             'admin_state_up': True,
                             'name': 'test_trunk', 'sub_ports': subports}
                    trunk_obj = self.trunk_plugin.create_trunk(
                        self.context, {'trunk': trunk})
                    yield {'trunk': trunk_obj}

    @contextlib.contextmanager
    def subport(self):
        with self.port() as child_port:
            subport = {'segmentation_type': 'vlan',
                       'segmentation_id': 123,
                       'port_id': child_port['port']['id']}
            yield subport


class TestTrunkV2Driver(base.V2DriverAdjustment, _TrunkDriverTest,
                        test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']

    def setUp(self):
        super(TestTrunkV2Driver, self).setUp()
        self.trunk_plugin = trunk_plugin.TrunkPlugin()
        self.trunk_plugin.add_segmentation_type(constants.VLAN,
                                                utils.is_valid_vlan_tag)


class TestTrunkV1Driver(_TrunkDriverTest, test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight']

    def setUp(self):
        super(TestTrunkV1Driver, self).setUp()
        self.trunk_plugin = trunk_plugin.TrunkPlugin()
        self.trunk_plugin.add_segmentation_type(constants.VLAN,
                                                utils.is_valid_vlan_tag)
