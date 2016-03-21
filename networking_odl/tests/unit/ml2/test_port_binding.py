# Copyright (c) 2016 OpenStack Foundation
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

import mock

from networking_odl.ml2 import legacy_port_binding
from networking_odl.ml2 import port_binding
from networking_odl.tests import base


class TestPortBindingManager(base.DietTestCase):

    def test_create(self):
        mgr = port_binding.PortBindingManager.create(
            name="legacy-port-binding")
        self.assertEqual("legacy-port-binding", mgr.name)
        self.assertIsInstance(mgr.controller,
                              legacy_port_binding.LegacyPortBindingManager)

    def test_create_with_nonexist_name(self):
        self.assertRaises(AssertionError,
                          port_binding.PortBindingManager.create,
                          name="nonexist-port-binding")

    @mock.patch.object(legacy_port_binding.LegacyPortBindingManager,
                       "bind_port")
    def test_bind_port(self, mock_method):
        port_context = mock.Mock()
        mgr = port_binding.PortBindingManager.create(
            name="legacy-port-binding")
        mgr.controller.bind_port(port_context)
        mock_method.assert_called_once_with(port_context)
