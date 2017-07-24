# Copyright (c) 2017 NEC Corp.
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

from neutron.common import utils
from oslo_config import cfg
from oslo_utils import uuidutils

from networking_odl.common import constants as odl_const
from networking_odl.db import models
from networking_odl.journal import journal
from networking_odl.tests.unit import base_v2


class JournalPeriodicProcessorTest(base_v2.OpenDaylightConfigBase):
    @mock.patch.object(journal.OpenDaylightJournalThread, 'set_sync_event')
    def test_processing(self, mock_journal):
        cfg.CONF.ml2_odl.sync_timeout = 0.1
        periodic_processor = journal.JournalPeriodicProcessor()
        self.addCleanup(periodic_processor.stop)
        periodic_processor.start()
        utils.wait_until_true(lambda: mock_journal.call_count > 1, 5, 0.1)


class OpenDaylightJournalThreadTest(base_v2.OpenDaylightTestCase):
    def setUp(self):
        super(OpenDaylightJournalThreadTest, self).setUp()
        self.journal = journal.OpenDaylightJournalThread()
        self.addCleanup(self.cleanup)

    @staticmethod
    def cleanup():
        journal.MAKE_URL.clear()

    def test_json_data(self):
        object_type = 'testobject'
        data = 'testdata'
        row = models.OpenDaylightJournal(object_type=object_type,
                                         object_uuid=uuidutils.generate_uuid(),
                                         operation=odl_const.ODL_CREATE,
                                         data=data)

        self.assertEqual("%ss" % object_type, self.journal._json_data(row)[1])

    def test_json_data_customized_url(self):
        object_type = 'randomtestobject'
        data = 'testdata'
        journal.register_url_builder(object_type, lambda row: row.object_type)
        row = models.OpenDaylightJournal(object_type=object_type,
                                         object_uuid=uuidutils.generate_uuid(),
                                         operation=odl_const.ODL_CREATE,
                                         data=data)

        url_param = self.journal._json_data(row)
        self.assertEqual(object_type, url_param[1])
