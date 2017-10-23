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

import fixtures
import mock

from neutron.common import utils
from oslo_config import cfg
from oslo_db import exception
from oslo_log import log as logging
from oslo_utils import uuidutils

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.db import models
from networking_odl.journal import dependency_validations
from networking_odl.journal import journal
from networking_odl.tests.unit import base_v2
from networking_odl.tests.unit.db import test_db


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

    def test_entry_reset_retries_exceptions(self):
        with mock.patch.object(db, 'update_db_row_state') as m:
            self._test_retry_exceptions(
                journal.entry_reset, m, True)

    @mock.patch.object(client.OpenDaylightRestClient, 'sendjson',
                       mock.Mock(side_effect=Exception))
    def test__sync_entry_update_state_by_retry_count_on_exception(self):
        entry = db.create_pending_row(self.db_session, *self.UPDATE_ROW)
        self.journal._max_retry_count = 1
        self.assertEqual(entry.retry_count, 0)
        self.journal._sync_entry(self.db_context, entry)
        self.assertEqual(entry.retry_count, 1)
        self.assertEqual(entry.state, odl_const.PENDING)
        self.journal._sync_entry(self.db_context, entry)
        self.assertEqual(entry.retry_count, 1)
        self.assertEqual(entry.state, odl_const.FAILED)

    def _test__sync_entry_logs(self, log_type):
        entry = db.create_pending_row(self.db_session, *self.UPDATE_ROW)
        logger = self.useFixture(fixtures.FakeLogger())

        self.journal._sync_entry(self.db_context, entry)

        self.assertIn(log_type, logger.output)

    def test__sync_entry_logs_processing(self):
        self._test__sync_entry_logs(journal.LOG_PROCESSING)

    def test__sync_entry_logs_completed(self):
        self._test__sync_entry_logs(journal.LOG_COMPLETED)

    @mock.patch.object(client.OpenDaylightRestClient, 'sendjson',
                       mock.Mock(side_effect=Exception))
    def test__sync_entry_logs_failed(self):
        self._test__sync_entry_logs(journal.LOG_ERROR_PROCESSING)


def _raise_DBReferenceError(*args, **kwargs):
    args = [mock.Mock(unsafe=True)] * 4
    e = exception.DBReferenceError(*args)
    raise e


class JournalTest(base_v2.OpenDaylightTestCase):
    @mock.patch.object(dependency_validations, 'calculate')
    @mock.patch.object(journal.db, 'create_pending_row',
                       side_effect=_raise_DBReferenceError)
    def test_record_triggers_retry_on_reference_error(self, mock_create_row,
                                                      mock_calculate):
        args = [mock.Mock(unsafe=True)] * 5
        self.assertRaises(exception.RetryRequest, journal.record, *args)

    def test_entry_complete_retries_exceptions(self):
        with mock.patch.object(db, 'update_db_row_state') as m:
            self._test_retry_exceptions(journal.entry_complete, m, True)

    def _test_entry_complete(self, retention, expected_length):
        self.cfg.config(completed_rows_retention=retention, group='ml2_odl')
        db.create_pending_row(self.db_session,
                              *test_db.DbTestCase.UPDATE_ROW)
        entry = db.get_all_db_rows(self.db_session)[-1]
        journal.entry_complete(self.db_context, entry)
        rows = db.get_all_db_rows(self.db_session)
        self.assertEqual(expected_length, len(rows))
        self.assertTrue(
            all(row.state == odl_const.COMPLETED for row in rows))

    def test_entry_complete_no_retention(self):
        self._test_entry_complete(0, 0)

    def test_entry_complete_with_retention(self):
        self._test_entry_complete(1, 1)

    def test_entry_complete_with_indefinite_retention(self):
        self._test_entry_complete(-1, 1)

    def test_entry_complete_with_retention_deletes_dependencies(self):
        self.cfg.config(completed_rows_retention=1, group='ml2_odl')
        db.create_pending_row(self.db_session,
                              *test_db.DbTestCase.UPDATE_ROW)
        entry = db.get_all_db_rows(self.db_session)[-1]
        db.create_pending_row(self.db_session,
                              *test_db.DbTestCase.UPDATE_ROW,
                              depending_on=[entry])
        dependant = db.get_all_db_rows(self.db_session)[-1]
        journal.entry_complete(self.db_context, entry)
        rows = db.get_all_db_rows(self.db_session)
        self.assertIn(entry, rows)
        self.assertEqual([], entry.dependencies)
        self.assertEqual([], dependant.depending_on)

    def test_entry_reset_retries_exceptions(self):
        with mock.patch.object(db, 'update_db_row_state') as m:
            self._test_retry_exceptions(journal.entry_reset, m, True)

    def test_entry_reset(self):
        db.create_pending_row(self.db_session,
                              *test_db.DbTestCase.UPDATE_ROW)
        db.create_pending_row(self.db_session,
                              *test_db.DbTestCase.UPDATE_ROW)
        entry = db.get_all_db_rows(self.db_session)[-1]
        entry.state = odl_const.PROCESSING
        self.db_session.merge(entry)
        self.db_session.flush()
        entry = db.get_all_db_rows(self.db_session)[-1]
        self.assertEqual(entry.state, odl_const.PROCESSING)
        journal.entry_reset(self.db_context, entry)
        rows = db.get_all_db_rows(self.db_session)
        self.assertEqual(2, len(rows))
        self.assertTrue(all(row.state == odl_const.PENDING for row in rows))

    def test_entry_set_retry_count_retries_exceptions(self):
        with mock.patch.object(db, 'update_pending_db_row_retry') as m:
            self._test_retry_exceptions(
                journal.entry_update_state_by_retry_count, m, True)

    def test_entry_set_retry_count(self):
        db.create_pending_row(self.db_session,
                              *test_db.DbTestCase.UPDATE_ROW)
        entry_baseline = db.get_all_db_rows(self.db_session)[-1]
        db.create_pending_row(self.db_session,
                              *test_db.DbTestCase.UPDATE_ROW)
        entry_target = db.get_all_db_rows(self.db_session)[-1]
        self.assertEqual(entry_target.retry_count, 0)
        self.assertEqual(entry_target.retry_count, entry_baseline.retry_count)
        self.assertEqual(entry_target.state, entry_baseline.state)

        journal.entry_update_state_by_retry_count(
            self.db_context, entry_target, 1)
        self.assertEqual(entry_target.retry_count, 1)
        self.assertEqual(entry_target.state, odl_const.PENDING)

        journal.entry_update_state_by_retry_count(
            self.db_context, entry_target, 1)
        self.assertEqual(entry_target.retry_count, 1)
        self.assertEqual(entry_target.state, odl_const.FAILED)
        self.assertNotEqual(entry_target.state, entry_baseline.state)
        self.assertNotEqual(entry_target.retry_count,
                            entry_baseline.retry_count)

    def test_record_logs_recording(self):
        logger = self.useFixture(fixtures.FakeLogger())
        journal.record(self.db_context, *self.UPDATE_ROW)
        for arg in self.UPDATE_ROW[0:3]:
            self.assertIn(arg, logger.output)

    def test_record_logs_dependencies(self):
        entry = db.create_pending_row(self.db_session, *self.UPDATE_ROW)

        logger = self.useFixture(fixtures.FakeLogger(level=logging.DEBUG))
        journal.record(self.db_context, *self.UPDATE_ROW)
        self.assertIn(str(entry.seqnum), logger.output)
