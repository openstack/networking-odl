# Copyright (c) 2015 OpenStack Foundation
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

from neutron.tests import base

from networking_odl.common import utils


class TestUtils(base.DietTestCase):

    # TODO(manjeets) remove this test once neutronify is
    # consolidated with make_plural
    def test_neutronify(self):
        self.assertEqual('a-b-c', utils.neutronify('a_b_c'))

    def test_neutronify_empty(self):
        self.assertEqual('', utils.neutronify(''))

    def test_make_url_object_in_resource_map(self):
        url_object = utils.make_url_object('policy')
        self.assertEqual('qos/policies', url_object)

    def test_make_url_object_conversion(self):
        self.assertEqual('networks', utils.make_url_object('network'))
        self.assertEqual('l2-gateways', utils.make_url_object('l2_gateway'))
