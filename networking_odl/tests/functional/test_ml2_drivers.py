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

from neutron.common import utils
from neutron.plugins.ml2 import config
from neutron.tests.unit.extensions import test_securitygroup
from neutron.tests.unit.plugins.ml2 import test_plugin

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.common import utils as odl_utils
from networking_odl.db import db
from networking_odl.tests.unit import test_base_db


class _OdlTestsBase(object):
    def setUp(self):
        config.cfg.CONF.set_override(
            'url', 'http://127.0.0.1:8181/controller/nb/v2/neutron', 'ml2_odl')
        config.cfg.CONF.set_override('username', 'admin', 'ml2_odl')
        config.cfg.CONF.set_override('password', 'admin', 'ml2_odl')
        config.cfg.CONF.set_override('mechanism_drivers',
                                     self._mechanism_drivers,
                                     group='ml2')
        self.client = client.OpenDaylightRestClient.create_client()
        super(_OdlTestsBase, self).setUp()

    def _get_odl_resource(self, resource_type, resource):
        return self.client.get_resource(
            resource_type, resource[resource_type]['id'])

    def _assert_resource_created(self, resource_type, resource):
        odl_resource = self._get_odl_resource(resource_type, resource)
        self.assertIsNotNone(odl_resource)

    def _test_resource_update(self, resource_type, resource):
        update_field = 'name'
        update_value = 'bubu'
        resource = self._get_odl_resource(resource_type, resource)
        self.assertNotEqual(update_value,
                            resource[resource_type][update_field])

        self._update(odl_utils.neutronify(resource_type + 's'),
                     resource[resource_type]['id'],
                     {resource_type: {update_field: update_value}})
        resource = self._get_odl_resource(resource_type, resource)
        self.assertEqual(update_value, resource[resource_type][update_field])

    def _test_resource_delete(self, resource_type, resource):
        self._delete(odl_utils.neutronify(resource_type + 's'),
                     resource[resource_type]['id'])
        self.assertIsNone(self._get_odl_resource(resource_type, resource))


class _DriverTest(_OdlTestsBase):

    def test_network_create(self):
        with self.network() as network:
            self._assert_resource_created(odl_const.ODL_NETWORK, network)

    def test_network_update(self):
        with self.network() as network:
            self._test_resource_update(odl_const.ODL_NETWORK, network)

    def test_network_delete(self):
        with self.network() as network:
            self._test_resource_delete(odl_const.ODL_NETWORK, network)

    def test_subnet_create(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self._assert_resource_created(odl_const.ODL_SUBNET, subnet)

    def test_subnet_update(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self._test_resource_update(odl_const.ODL_SUBNET, subnet)

    def test_subnet_delete(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                self._test_resource_delete(odl_const.ODL_SUBNET, subnet)

    def test_port_create(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                with self.port(subnet=subnet) as port:
                    self._assert_resource_created(odl_const.ODL_PORT, port)

    def test_port_update(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                with self.port(subnet=subnet) as port:
                    self._test_resource_update(odl_const.ODL_PORT, port)

    def test_port_delete(self):
        with self.network() as network:
            with self.subnet(network=network) as subnet:
                with self.port(subnet=subnet) as port:
                    self._test_resource_delete(odl_const.ODL_PORT, port)


class _DriverSecGroupsTests(_OdlTestsBase):

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
            self._assert_resource_created(odl_const.ODL_SG, sg)

    def test_security_group_update(self):
        with self.security_group() as sg:
            self._test_resource_update(odl_const.ODL_SG, sg)

    def test_security_group_delete(self):
        with self.security_group() as sg:
            self._test_resource_delete(odl_const.ODL_SG, sg)

    def test_security_group_rule_create(self):
        with self.security_group() as sg:
            sg_id = sg[odl_const.ODL_SG]['id']
            with self.security_group_rule(security_group_id=sg_id) as sg_rule:
                self._assert_resource_created(odl_const.ODL_SG_RULE, sg_rule)

    def test_security_group_rule_delete(self):
        with self.security_group() as sg:
            sg_id = sg[odl_const.ODL_SG]['id']
            with self.security_group_rule(security_group_id=sg_id) as sg_rule:
                self._test_resource_delete(odl_const.ODL_SG_RULE, sg_rule)


class TestV1Driver(_DriverTest, test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight']


class TestV1DriverSecGroups(_DriverSecGroupsTests,
                            test_securitygroup.SecurityGroupsTestCase,
                            test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight']


class _V2DriverAdjustment(object):
    def _get_odl_resource(self, resource_type, resource):
        def _no_journal_rows():
            pending_rows = db.get_all_db_rows_by_state(
                self.db_session, odl_const.PENDING)
            processing_rows = db.get_all_db_rows_by_state(
                self.db_session, odl_const.PROCESSING)
            return len(pending_rows) == 0 and len(processing_rows) == 0

        utils.wait_until_true(_no_journal_rows, 5, 0.5)

        return super(_V2DriverAdjustment, self)._get_odl_resource(
            resource_type, resource)


class TestV2Driver(_V2DriverAdjustment, _DriverTest,
                   test_base_db.ODLBaseDbTestCase,
                   test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']


class TestV2DriverSecGroups(_V2DriverAdjustment, _DriverSecGroupsTests,
                            test_securitygroup.SecurityGroupsTestCase,
                            test_base_db.ODLBaseDbTestCase,
                            test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']
