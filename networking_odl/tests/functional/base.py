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

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.common import utils as odl_utils
from networking_odl.db import db
from networking_odl.tests.unit import test_base_db


class OdlTestsBase(object):
    def setUp(self):
        config.cfg.CONF.set_override(
            'url', 'http://127.0.0.1:8181/controller/nb/v2/neutron', 'ml2_odl')
        config.cfg.CONF.set_override('username', 'admin', 'ml2_odl')
        config.cfg.CONF.set_override('password', 'admin', 'ml2_odl')
        config.cfg.CONF.set_override('mechanism_drivers',
                                     self._mechanism_drivers,
                                     group='ml2')
        config.cfg.CONF.set_override('extension_drivers',
                                     ['qos', 'port_security'],
                                     group='ml2')
        self.client = client.OpenDaylightRestClient.create_client()
        super(OdlTestsBase, self).setUp()

    def get_odl_resource(self, resource_type, resource):
        return self.client.get_resource(
            resource_type, resource[resource_type]['id'])

    def assert_resource_created(self, resource_type, resource):
        odl_resource = self.get_odl_resource(resource_type, resource)
        self.assertIsNotNone(odl_resource)

    def resource_update_test(self, resource_type, resource):
        update_field = 'name'
        update_value = 'bubu'
        resource = self.get_odl_resource(resource_type, resource)
        self.assertNotEqual(update_value,
                            resource[resource_type][update_field])

        self._update(odl_utils.make_url_object(resource_type),
                     resource[resource_type]['id'],
                     {resource_type: {update_field: update_value}})
        resource = self.get_odl_resource(resource_type, resource)
        self.assertEqual(update_value, resource[resource_type][update_field])

    def resource_delete_test(self, resource_type, resource):
        self._delete(odl_utils.make_url_object(resource_type),
                     resource[resource_type]['id'])
        self.assertIsNone(self.get_odl_resource(resource_type, resource))


class V2DriverAdjustment(test_base_db.ODLBaseDbTestCase):
    def get_odl_resource(self, resource_type, resource):
        def no_journal_rows():
            pending_rows = db.get_all_db_rows_by_state(
                self.db_session, odl_const.PENDING)
            processing_rows = db.get_all_db_rows_by_state(
                self.db_session, odl_const.PROCESSING)
            return len(pending_rows) == 0 and len(processing_rows) == 0

        utils.wait_until_true(no_journal_rows, 5, 0.5)

        return super(V2DriverAdjustment, self).get_odl_resource(
            resource_type, resource)
