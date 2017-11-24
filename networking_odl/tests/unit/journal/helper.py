# Copyright (c) 2017 OpenStack Foundation.
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

from networking_odl.journal import base_driver


TEST_UUID = 'bd8db3a8-2b30-4083-a8b3-b3fd46401142'
TEST_PLUGIN = 'test_plugin'
TEST_RESOURCE1 = 'test_resource1'
TEST_RESOURCE2 = 'test_resource2'
TEST_RESOURCE1_SUFFIX = 'test_resource1s'
TEST_RESOURCE2_SUFFIX = 'test_resource2s'
INVALID_RESOURCE = 'invalid_resource'
INVALID_PLUGIN = 'invalid_plugin'
INVALID_METHOD = 'invalid_method_name'


class TestPlugin(object):
    def get_test_resource1s(self, context):
        return [{'id': 'test_id1'}, {'id': 'test_id2'}]

    def get_test_resource2s(self, context):
        return [{'id': 'test_id3'}, {'id': 'test_id4'}]

    def get_test_resource1(self, context, id_):
        return {'id': id_}


class TestDriver(base_driver.ResourceBaseDriver):
    RESOURCES = {
        TEST_RESOURCE1: TEST_RESOURCE1_SUFFIX,
        TEST_RESOURCE2: TEST_RESOURCE2_SUFFIX
    }
    plugin_type = TEST_PLUGIN

    def __init__(self):
        super(TestDriver, self).__init__()
