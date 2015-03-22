# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
test_lbaas_odl
----------------------------------

Tests for the LBaaS plugin for networking-odl.
"""

import mock

from networking_odl.lbaas import driver_v2 as lbaas_odl

from neutron.tests import base


class TestODL_LBaaS(base.BaseTestCase):

    def test_init(self):
        # just create an instance of OpenDaylightLbaasDriverV2
        self.plugin = mock.Mock()
        lbaas_odl.OpenDaylightLbaasDriverV2(self.plugin)
