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

from neutron.tests.unit.extensions import test_securitygroup
from neutron.tests.unit.plugins.ml2 import test_plugin

from networking_odl.common import constants as odl_const
from networking_odl.tests.functional import base


class _DriverTest(base.OdlTestsBase):

    def test_network_create(self):
        with self.network() as network:
            self.assert_resource_created(odl_const.ODL_NETWORK, network)

    def test_network_update(self):
        with self.network() as network:
            self.resource_update_test(odl_const.ODL_NETWORK, network)

    def test_network_delete(self):
        with self.network() as network:
            self.resource_delete_test(odl_const.ODL_NETWORK, network)

    def test_subnet_create(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self.assert_resource_created(odl_const.ODL_SUBNET, subnet)

    def test_subnet_update(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self.resource_update_test(odl_const.ODL_SUBNET, subnet)

    def test_subnet_delete(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self.resource_delete_test(odl_const.ODL_SUBNET, subnet)

    def test_port_create(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                with self.port(subnet=subnet) as port:
                    self.assert_resource_created(odl_const.ODL_PORT, port)

    def test_port_update(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                with self.port(subnet=subnet) as port:
                    self.resource_update_test(odl_const.ODL_PORT, port)

    def test_port_delete(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                with self.port(subnet=subnet) as port:
                    self.resource_delete_test(odl_const.ODL_PORT, port)


class _DriverSecGroupsTests(base.OdlTestsBase):

    # Override default behavior so that extension manager is used, otherwise
    # we can't test security groups.
    def setup_parent(self):
        """Perform parent setup with the common plugin configuration class."""
        ext_mgr = (
            test_securitygroup.SecurityGroupTestExtensionManager())
        # Ensure that the parent setup can be called without arguments
        # by the common configuration setUp.
        parent_setup = functools.partial(
            super(test_plugin.Ml2PluginV2TestCase, self).setUp,
            plugin=test_plugin.PLUGIN_NAME,
            ext_mgr=ext_mgr,
        )
        self.useFixture(test_plugin.Ml2ConfFixture(parent_setup))

    def test_security_group_create(self):
        with self.security_group() as sg:
            self.assert_resource_created(odl_const.ODL_SG, sg)

    def test_security_group_update(self):
        with self.security_group() as sg:
            self.resource_update_test(odl_const.ODL_SG, sg)

    def test_security_group_delete(self):
        with self.security_group() as sg:
            self.resource_delete_test(odl_const.ODL_SG, sg)

    def test_security_group_rule_create(self):
        with self.security_group() as sg:
            sg_id = sg[odl_const.ODL_SG]['id']
            with self.security_group_rule(security_group_id=sg_id) as sg_rule:
                self.assert_resource_created(odl_const.ODL_SG_RULE, sg_rule)

    def test_security_group_rule_delete(self):
        with self.security_group() as sg:
            sg_id = sg[odl_const.ODL_SG]['id']
            with self.security_group_rule(security_group_id=sg_id) as sg_rule:
                self.resource_delete_test(odl_const.ODL_SG_RULE, sg_rule)


class TestV2Driver(base.V2DriverAdjustment, _DriverTest,
                   test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']


class TestV2DriverSecGroups(base.V2DriverAdjustment, _DriverSecGroupsTests,
                            test_securitygroup.SecurityGroupsTestCase,
                            test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']
