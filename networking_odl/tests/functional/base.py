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
import os

from neutron.common import utils
from neutron.tests import base
from neutron.tests.common import helpers
from neutron.tests.unit.plugins.ml2 import test_plugin
from oslo_config import cfg
from oslo_config import fixture as config_fixture

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.common import utils as odl_utils
from networking_odl.db import db
from networking_odl.tests import base as test_base
from networking_odl.tests.unit import test_base_db


class OdlTestsBase(object):
    #  this is stolen from neutron.tests.functional.base
    # This is the directory from which infra fetches log files
    # for functional tests.
    DEFAULT_LOG_DIR = os.path.join(helpers.get_test_log_path(),
                                   'functional-logs')

    def setUp(self):
        self.cfg = self.useFixture(config_fixture.Config())
        self.cfg.config(
            url='http://127.0.0.1:8181/controller/nb/v2/neutron',
            group='ml2_odl')
        self.cfg.config(username='admin', group='ml2_odl')
        self.cfg.config(password='admin', group='ml2_odl')
        self.cfg.config(mechanism_drivers=self._mechanism_drivers, group='ml2')
        self.cfg.config(extension_drivers=[
                        'qos', 'port_security'], group='ml2')
        self.client = client.OpenDaylightRestClient.create_client()
        super(OdlTestsBase, self).setUp()
        base.setup_test_logging(
            cfg.CONF, self.DEFAULT_LOG_DIR, "%s.txt" % self.id())

    def setup_parent(self):
        """Perform parent setup with the common plugin configuration class."""
        # Ensure that the parent setup can be called without arguments
        # by the common configuration setUp.
        service_plugins = {'l3_plugin_name': self.l3_plugin}
        service_plugins.update(self.get_additional_service_plugins())
        parent_setup = functools.partial(
            super(test_plugin.Ml2PluginV2TestCase, self).setUp,
            plugin=self.get_plugins(),
            ext_mgr=self.get_ext_managers(),
            service_plugins=service_plugins
        )
        self.useFixture(test_plugin.Ml2ConfFixture(parent_setup))

    def get_plugins(self):
        return test_plugin.PLUGIN_NAME

    def get_ext_managers(self):
        return None

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
    def setUp(self):
        super(V2DriverAdjustment, self).setUp()
        self.useFixture(test_base.JournalWorkerPidFileFixture())

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
