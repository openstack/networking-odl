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

from networking_odl.common import client
from networking_odl.journal import journal
from networking_odl.ml2 import mech_driver_v2
from networking_odl.tests import base
from networking_odl.tests.unit import test_base_db


class OpenDaylightConfigBase(test_plugin.Ml2PluginV2TestCase,
                             test_base_db.ODLBaseDbTestCase):
    def setUp(self):
        self.journal_thread_fixture = self.useFixture(
            base.OpenDaylightJournalThreadFixture())
        self.useFixture(base.OpenDaylightRestClientFixture())
        self.useFixture(base.OpenDaylightFullSyncFixture())
        super(OpenDaylightConfigBase, self).setUp()
        self.thread = journal.OpenDaylightJournalThread()

    def run_journal_processing(self):
        """Cause the journal to process the first pending entry"""
        self.thread.sync_pending_entries()


class OpenDaylightTestCase(OpenDaylightConfigBase):
    def setUp(self):
        self.mock_sendjson = mock.patch.object(client.OpenDaylightRestClient,
                                               'sendjson').start()
        super(OpenDaylightTestCase, self).setUp()
        self.port_create_status = 'DOWN'
        self.mech = mech_driver_v2.OpenDaylightMechanismDriver()
        self.mock_sendjson.side_effect = self.check_sendjson

    def check_sendjson(self, method, urlpath, obj):
        self.assertFalse(urlpath.startswith("http://"))
