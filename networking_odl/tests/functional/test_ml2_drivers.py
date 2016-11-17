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

from neutron.common import utils
from neutron.plugins.ml2 import config
from neutron.tests.unit.plugins.ml2 import test_plugin

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.tests.unit import test_base_db


class _DriverTest(object):

    def setUp(self):
        config.cfg.CONF.set_override(
            'url', 'http://127.0.0.1:8181/controller/nb/v2/neutron', 'ml2_odl')
        config.cfg.CONF.set_override('username', 'admin', 'ml2_odl')
        config.cfg.CONF.set_override('password', 'admin', 'ml2_odl')
        config.cfg.CONF.set_override('mechanism_drivers',
                                     self._mechanism_drivers,
                                     group='ml2')
        self.client = client.OpenDaylightRestClient.create_client()
        super(_DriverTest, self).setUp()

    def _get_odl_resource(self, resource_type, resource):
        return self.client.get_resource(
            resource_type, resource[resource_type]['id'])

    def _assert_resource_created(self, resource_type, resource):
        odl_resource = self._get_odl_resource(resource_type, resource)
        self.assertIsNotNone(odl_resource)

    def test_network_create(self):
        with self.network() as network:
            self._assert_resource_created(odl_const.ODL_NETWORK, network)

    def _test_resource_update(self, resource_type, resource):
        update_field = 'name'
        update_value = 'bubu'
        resource = self._get_odl_resource(resource_type, resource)
        self.assertNotEqual(update_value,
                            resource[resource_type][update_field])

        self._update(resource_type + 's',
                     resource[resource_type]['id'],
                     {resource_type: {update_field: update_value}})
        resource = self._get_odl_resource(resource_type, resource)
        self.assertEqual(update_value, resource[resource_type][update_field])

    def test_network_update(self):
        with self.network() as network:
            self._test_resource_update(odl_const.ODL_NETWORK, network)

    def _test_resource_delete(self, resource_type, resource):
        self._delete(resource_type + 's', resource[resource_type]['id'])
        self.assertIsNone(self._get_odl_resource(resource_type, resource))

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


class TestV1Driver(_DriverTest, test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight']


class TestV2Driver(_DriverTest, test_base_db.ODLBaseDbTestCase,
                   test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']

    def _get_odl_resource(self, resource_type, resource):
        def _no_journal_rows():
            pending_rows = db.get_all_db_rows_by_state(
                self.db_session, odl_const.PENDING)
            processing_rows = db.get_all_db_rows_by_state(
                self.db_session, odl_const.PROCESSING)
            return len(pending_rows) == 0 and len(processing_rows) == 0

        utils.wait_until_true(_no_journal_rows, 5, 0.5)

        return super(TestV2Driver, self)._get_odl_resource(
            resource_type, resource)
