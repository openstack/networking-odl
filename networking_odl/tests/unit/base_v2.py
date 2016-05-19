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

from neutron.tests.unit.plugins.ml2 import test_plugin
from oslo_config import cfg

from networking_odl.common import client
from networking_odl.journal import journal
from networking_odl.journal import maintenance
from networking_odl.ml2 import mech_driver_v2
from networking_odl.tests import base
from networking_odl.tests.unit import test_base_db


class OpenDaylightConfigBase(test_plugin.Ml2PluginV2TestCase,
                             test_base_db.ODLBaseDbTestCase):
    def setUp(self):
        self.useFixture(base.OpenDaylightRestClientFixture())
        super(OpenDaylightConfigBase, self).setUp()
        cfg.CONF.set_override('mechanism_drivers',
                              ['logger', 'opendaylight_v2'], 'ml2')
        cfg.CONF.set_override('extension_drivers',
                              ['port_security', 'qos'], 'ml2')
        self.mock_sync_thread = mock.patch.object(
            journal.OpendaylightJournalThread, 'start_odl_sync_thread').start()
        self.mock_mt_thread = mock.patch.object(
            maintenance.MaintenanceThread, 'start').start()


class OpenDaylightTestCase(OpenDaylightConfigBase):
    def setUp(self):
        super(OpenDaylightTestCase, self).setUp()
        self.port_create_status = 'DOWN'
        self.mech = mech_driver_v2.OpenDaylightMechanismDriver()
        self.mock_sendjson = mock.patch.object(client.OpenDaylightRestClient,
                                               'sendjson').start()
        self.mock_sendjson.side_effect = self.check_sendjson

    def check_sendjson(self, method, urlpath, obj):
        self.assertFalse(urlpath.startswith("http://"))
