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
test_fwaas_odl
----------------------------------

Tests for the L3 FWaaS plugin for networking-odl.
"""

from networking_odl.fwaas import driver as fwaas_odl

from neutron.tests import base


class TestODL_FWaaS(base.BaseTestCase):

    def test_init(self):
        # just create an instance of OpenDaylightFwaasDriver
        fwaas_odl.OpenDaylightFwaasDriver()
