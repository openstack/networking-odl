#
# Copyright (C) 2016 Red Hat, Inc.
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

import functools

from neutron.tests.unit.extensions import test_l3
from neutron.tests.unit.plugins.ml2 import test_plugin
from neutron_lib import constants as q_const

from networking_odl.common import constants as odl_const
from networking_odl.tests.functional import base


class _TestL3Base(test_l3.L3NatTestCaseMixin, base.OdlTestsBase):

    # Override default behavior so that extension manager is used, otherwise
    # we can't test security groups.
    def setup_parent(self):
        """Perform parent setup with the common plugin configuration class."""
        ext_mgr = test_l3.L3TestExtensionManager()

        # Ensure that the parent setup can be called without arguments
        # by the common configuration setUp.
        parent_setup = functools.partial(
            super(test_plugin.Ml2PluginV2TestCase, self).setUp,
            plugin=test_plugin.PLUGIN_NAME,
            ext_mgr=ext_mgr,
            service_plugins={'l3_plugin_name': self.l3_plugin},

        )
        self.useFixture(test_plugin.Ml2ConfFixture(parent_setup))

    def test_router_create(self):
        with self.router() as router:
            self.assert_resource_created(odl_const.ODL_ROUTER, router)

    def test_router_update(self):
        with self.router() as router:
            self.resource_update_test(odl_const.ODL_ROUTER, router)

    def test_router_delete(self):
        with self.router() as router:
            self.resource_delete_test(odl_const.ODL_ROUTER, router)

    def test_floatingip_create(self):
        with self.floatingip_with_assoc() as fip:
            self.assert_resource_created(odl_const.ODL_FLOATINGIP, fip)

        # Test FIP was deleted since the code creating the FIP deletes it
        # once the context block exists.
        odl_fip = self.get_odl_resource(odl_const.ODL_FLOATINGIP, fip)
        self.assertIsNone(odl_fip)

    def test_floatingip_status_with_port(self):
        with self.floatingip_with_assoc() as fip:
            self.assertEqual(
                q_const.FLOATINGIP_STATUS_ACTIVE,
                fip['floatingip']['status'])

    def test_floatingip_status_without_port(self):
        with self.subnet() as subnet:
            with self.floatingip_no_assoc(subnet) as fip:
                # status should be down when floating ip
                # is not associated to any port
                self.assertEqual(
                    q_const.FLOATINGIP_STATUS_DOWN,
                    fip['floatingip']['status'])

    def test_floatingip_dissociate_port(self):
        with self.floatingip_with_assoc() as fip:
            portid = fip['floatingip']['port_id']
            self.assertIsNotNone(portid)
            self._delete(odl_const.ODL_PORTS, portid)
            updated_fip = self.get_odl_resource(odl_const.ODL_FLOATINGIP, fip)
            self.assertNotIn('port_id', updated_fip['floatingip'].keys())


class TestL3PluginV1(_TestL3Base, test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight']
    l3_plugin = 'odl-router'


class TestL3PluginV2(base.V2DriverAdjustment, _TestL3Base,
                     test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']
    l3_plugin = 'odl-router_v2'
