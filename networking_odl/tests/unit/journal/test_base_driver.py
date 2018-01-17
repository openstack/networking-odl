# Copyright (c) 2017 NEC Corp
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

from neutron_lib.plugins import directory

from networking_odl.common import exceptions
from networking_odl.journal import base_driver
from networking_odl.tests.unit import test_base_db

TEST_PLUGIN = 'test_plugin'
TEST_RESOURCE1 = 'test_resource1'
TEST_RESOURCE2 = 'test_resource2'
TEST_RESOURCE1_SUFFIX = 'test_resource1s'
TEST_RESOURCE2_SUFFIX = 'test_resource2s'
INVALID_RESOURCE = 'invalid_resource'
INVALID_PLUGIN = 'invalid_plugin'


class TestPlugin(object):
    def get_test_resource1s(self, context):
        return [{'id': 'test_id1'}, {'id': 'test_id2'}]

    def get_test_resource2s(self, context):
        return [{'id': 'test_id3'}, {'id': 'test_id4'}]


class TestDriver(base_driver.ResourceBaseDriver):
    RESOURCES = {
        TEST_RESOURCE1: TEST_RESOURCE1_SUFFIX,
        TEST_RESOURCE2: TEST_RESOURCE2_SUFFIX
    }
    plugin_type = TEST_PLUGIN

    def __init__(self):
        super(TestDriver, self).__init__()


class BaseDriverTestCase(test_base_db.ODLBaseDbTestCase):
    def setUp(self):
        super(BaseDriverTestCase, self).setUp()
        self.test_driver = TestDriver()
        self.plugin = TestPlugin()
        directory.add_plugin(TEST_PLUGIN, self.plugin)
        self.addCleanup(directory.add_plugin, TEST_PLUGIN, None)

    def test_get_resource_driver(self):
        for resource, resource_suffix in self.test_driver.RESOURCES.items():
            driver = base_driver.get_driver(resource)
            self.assertEqual(driver, self.test_driver)
            self.assertEqual(driver.plugin_type, TEST_PLUGIN)
            self.assertEqual(self.test_driver.RESOURCES.get(resource),
                             resource_suffix)

    def non_existing_plugin_cleanup(self):
        self.test_driver.plugin_type = TEST_PLUGIN

    def test_non_existing_plugin(self):
        self.test_driver.plugin_type = INVALID_PLUGIN
        self.addCleanup(self.non_existing_plugin_cleanup)
        self.assertIsNone(self.test_driver.plugin)

    def test_get_non_existing_resource_driver(self):
        self.assertRaises(exceptions.ResourceNotRegistered,
                          base_driver.get_driver, INVALID_RESOURCE)

    def test_get_resources_for_full_sync(self):
        received_resources = self.test_driver.get_resources_for_full_sync(
            self.db_context,
            TEST_RESOURCE1)
        resources = self.plugin.get_test_resource1s(self.db_context)
        for resource in resources:
            self.assertIn(resource, received_resources)

    def test_get_non_existing_resources_for_full_sync(self):
        self.assertRaises(exceptions.UnsupportedResourceType,
                          self.test_driver.get_resources_for_full_sync,
                          self.db_context, INVALID_RESOURCE)
