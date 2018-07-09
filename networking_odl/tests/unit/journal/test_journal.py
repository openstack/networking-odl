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

import os
import signal

import fixtures
import mock

from neutron.common import utils
from oslo_db import exception
from oslo_log import log as logging
from oslo_service.tests import test_service
from oslo_utils import uuidutils

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.db import models
from networking_odl.journal import cleanup
from networking_odl.journal import dependency_validations
from networking_odl.journal import full_sync
from networking_odl.journal import journal
from networking_odl.journal import periodic_task
from networking_odl.journal import recovery
from networking_odl.journal import worker
from networking_odl.tests import base
from networking_odl.tests.unit import base_v2
from networking_odl.tests.unit.db import test_db


PROCESS_RUNNING_STATUSES = ('S', 'R', 'D')


class JournalPeriodicProcessorTest(base_v2.OpenDaylightConfigBase,
                                   test_service.ServiceTestBase):
    def setUp(self):
        super(JournalPeriodicProcessorTest, self).setUp()
        self.periodic_task_fixture = self.useFixture(
            base.OpenDaylightPeriodicTaskFixture())
        self.cfg.config(sync_timeout=0.1, group='ml2_odl')

    def _create_periodic_processor(self):
        periodic_processor = worker.JournalPeriodicProcessor()
        self.addCleanup(periodic_processor.stop)
        return periodic_processor

    def _get_pid_status(self, pid):
        """Allows to query a system process based on the PID

        It will use `ps` to query the pid, it's state and the command.

        :param pid: An integer with the Process ID number
        :returns: A tuple of strings with the command and the running status
                  in a single char as defined in the manpage PS(1) under
                  PROCESS STATE CODES.
        """
        with os.popen('ps ax -o pid,state,cmd') as f:
            # Skip ps header
            f.readline()

            processes = (l.strip().split()[:3] for l in f)

            return next(((c, s) for p, s, c in processes if int(p) == pid),
                        (None, None))

    def _kill_process(self, pid):
        if self._get_pid_status(pid)[1] in PROCESS_RUNNING_STATUSES:
            os.kill(pid, signal.SIGKILL)

    def mock_object_with_ipc(self, target, attribute, pre_hook=None):
            patcher = mock.patch.object(target, attribute, autospec=True)
            c2p_read = self.create_ipc_for_mock(patcher, pre_hook)
            return c2p_read

    def create_ipc_for_mock(self, patcher, pre_hook=None):
        # NOTE(mpeterson): The following pipe is being used because this is
        # testing something inter processeses and we need to have a value on
        # the side of the test processes to know it succeeded with the
        # operation. A pipe provide a way for two processes to communicate.
        # The was_called method will be called by the worker process while
        # the test process will read the result on c2p_read.
        c2p_read, c2p_write = os.pipe()

        def close_pipe_end(fd):
            try:
                os.close(fd)
            except OSError:
                print('failed closing: %s' % fd)

        # First we want to close the write, to unlock any running read()
        self.addCleanup(close_pipe_end, c2p_read)
        self.addCleanup(close_pipe_end, c2p_write)

        mock_ = patcher.start()
        self.addCleanup(patcher.stop)

        def was_called(*args, **kwargs):
            # OSError is caught because start is called twice on the worker
            # and the second time the pipe is already closed.
            try:
                os.close(c2p_read)
                try:
                    if pre_hook:
                        pre_hook(*args, **kwargs)
                    os.write(c2p_write, b'1')
                except Exception:
                    # This is done so any read on the pipe is unblocked.
                    os.write(c2p_write, b'0')
                finally:
                    os.close(c2p_write)
            except OSError:
                pass

        mock_.side_effect = was_called

        return c2p_read

    def assert_ipc_mock_called(self, c2p_read):
        # If it timeouts on the read then it means the function was
        # not called.
        called = int(os.read(c2p_read, 1))

        self.assertEqual(called, 1,
                         'The IPC mock was called but during the '
                         'execution an exception was raised')

    @mock.patch.object(journal.OpenDaylightJournalThread, 'set_sync_event')
    def test_processing(self, mock_journal):
        periodic_processor = self._create_periodic_processor()
        periodic_processor.start()
        utils.wait_until_true(lambda: mock_journal.call_count > 1, 5, 0.1)

    @mock.patch.object(journal.OpenDaylightJournalThread, 'start')
    @mock.patch.object(journal.OpenDaylightJournalThread, 'stop')
    def test_stops_journal_sync_thread(self, mock_stop, mock_start):
        periodic_processor = self._create_periodic_processor()
        periodic_processor.start()
        periodic_processor.stop()
        mock_stop.assert_called_once()
        mock_start.assert_called_once()

    def test_allow_multiple_starts_gracefully(self):
        periodic_processor = self._create_periodic_processor()
        periodic_processor.start()
        periodic_processor.stop()

        try:
            periodic_processor.start()
        except RuntimeError:
            self.fail('Calling a start() after a stop() should be allowed')

    def test_multiple_starts_without_stop_throws_exception(self):
        periodic_processor = self._create_periodic_processor()
        periodic_processor.start()

        self.assertRaises(RuntimeError, periodic_processor.start)

    def test_call_stop_without_calling_start(self):
        periodic_processor = self._create_periodic_processor()

        try:
            periodic_processor.stop()
        except AttributeError:
            self.fail('start() was not called before calling stop()')

    def assert_process_running(self, pid):
        cmd, state = self._get_pid_status(pid)
        self.assertIn(state, PROCESS_RUNNING_STATUSES)
        return cmd

    def _create_periodic_processor_ipc_fork(self, target, pre_hook=None):
        self._setup_mocks_for_periodic_task()

        real_start = worker.JournalPeriodicProcessor.start
        pipe_start = self.mock_object_with_ipc(worker.JournalPeriodicProcessor,
                                               'start', real_start)

        c2p_read = self.mock_object_with_ipc(worker.JournalPeriodicProcessor,
                                             target, pre_hook)

        pid = self._spawn_service(
            service_maker=lambda: worker.JournalPeriodicProcessor())
        self.addCleanup(self._kill_process, pid)

        # Allow the process to spawn and signal handling to be registered
        self.assert_ipc_mock_called(pipe_start)

        return pid, c2p_read

    @mock.patch.object(periodic_task.PeriodicTask, 'execute_ops',
                       new=mock.Mock())
    @mock.patch.object(journal.OpenDaylightJournalThread,
                       'sync_pending_entries', new=mock.Mock())
    def test_handle_sighup_gracefully(self):
        real_reset = worker.JournalPeriodicProcessor.reset
        pid, c2p_read = self._create_periodic_processor_ipc_fork('reset',
                                                                 real_reset)

        cmd = self.assert_process_running(pid)

        os.kill(pid, signal.SIGHUP)

        self.assert_ipc_mock_called(c2p_read)

        new_cmd = self.assert_process_running(pid)
        self.assertEqual(cmd, new_cmd)

    def _setup_mocks_for_periodic_task(self, executed_recently=False):
        mock_db_module = mock.MagicMock(spec=db)
        mock_db_module.was_periodic_task_executed_recently.return_value = \
            executed_recently
        mock_db = mock.patch('networking_odl.journal.periodic_task.db',
                             mock_db_module)
        mock_db.start()
        self.addCleanup(mock_db.stop)

    @mock.patch.object(cleanup, 'delete_completed_rows')
    @mock.patch.object(cleanup, 'cleanup_processing_rows')
    @mock.patch.object(full_sync, 'full_sync')
    @mock.patch.object(recovery, 'journal_recovery')
    # ^^ The above mocks represent the required calling order starting from
    # top. Use decorators *only* to specify the stack order.
    def test_maintenance_task_correctly_registered(self, *stack_order):
        calls = []
        for item in reversed(stack_order):
            calls.append(mock.call(item))

        with mock.patch.object(
                periodic_task.PeriodicTask,
                'register_operation') as register_operation_mock:
            periodic_processor = self._create_periodic_processor()
            periodic_processor._start_maintenance_task()
            register_operation_mock.assert_has_calls(calls)

    def test_maintenance_task_started(self):
        self.periodic_task_fixture.task_start_mock.stop()
        mock_start = self.periodic_task_fixture.task_start_mock.start()
        periodic_processor = self._create_periodic_processor()
        periodic_processor.start()
        periodic_processor._maintenance_task = mock.MagicMock()

        mock_start.assert_called_once()

    @mock.patch.object(periodic_task.PeriodicTask, 'execute_ops',
                       new=mock.Mock())
    def test_reset_called_on_sighup(self):
        pid, c2p_read = self._create_periodic_processor_ipc_fork('reset')

        self.assert_process_running(pid)

        os.kill(pid, signal.SIGHUP)

        self.assert_ipc_mock_called(c2p_read)

    @mock.patch.object(periodic_task.PeriodicTask, 'execute_ops')
    def test_reset_fires_maintenance_task(self, execute_mock):
        periodic_processor = self._create_periodic_processor()

        periodic_processor._start_maintenance_task()
        execute_mock.reset_mock()

        periodic_processor.reset()

        execute_mock.assert_has_calls([mock.call(forced=True)])

    def test_reset_succeeeds_when_maintenance_task_not_setup(self):
        periodic_processor = self._create_periodic_processor()

        # NOTE(mpeterson): This tests that if calling reset without setting up
        # the maintenance task then it would not raise an exception and just
        # proceed as usual.
        periodic_processor.reset()

    @mock.patch.object(periodic_task.PeriodicTask, 'execute_ops')
    def test_start_fires_maintenance_task(self, execute_mock):
        periodic_processor = self._create_periodic_processor()

        periodic_processor.start()

        execute_mock.called_once_with([mock.call(forced=True)])

    def test_creates_pidfile(self):
        periodic_processor = self._create_periodic_processor()
        periodic_processor._create_pidfile()

        pidfile = str(periodic_processor.pidfile)
        self.assertTrue(os.path.isfile(pidfile))

        with open(pidfile) as f:
            pid = int(f.readline())

        self.assertEqual(pid, os.getpid())

        # NOTE(mpeterson): to avoid showing an expected exception while
        # running the next assert
        with mock.patch('neutron.agent.linux.daemon.LOG', autospec=True):
            self.assertRaises(
                SystemExit,
                worker.JournalPeriodicProcessor()._create_pidfile
            )

    @mock.patch.object(worker.JournalPeriodicProcessor, '_create_pidfile')
    @mock.patch.object(worker.JournalPeriodicProcessor, '_delete_pidfile')
    def test_pidfile_handling_on_start_stop(self, mock_create, mock_delete):
        periodic_processor = self._create_periodic_processor()
        periodic_processor.start()
        periodic_processor.stop()

        mock_create.assert_called_once()
        mock_delete.assert_called_once()

    def test_deletes_pidfile(self):
        atexit_mock = self.journal_thread_fixture.remock_atexit()

        periodic_processor = self._create_periodic_processor()
        periodic_processor.start()

        pidfile = str(periodic_processor.pidfile)
        self.assertTrue(os.path.isfile(pidfile))

        periodic_processor._delete_pidfile()

        self.assertFalse(os.path.isfile(pidfile))

        atexit_mock.assert_called_once_with(periodic_processor._delete_pidfile)

    def test_atexit_delete_pidfile_registered_only_once(self):
        atexit_mock = self.journal_thread_fixture.remock_atexit()
        periodic_processor = self._create_periodic_processor()

        for _ in range(0, 2):
            periodic_processor.start()
            periodic_processor.stop()

        atexit_mock.assert_called_once()


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
            self._test_retry_exceptions(journal.entry_reset, m)

    @test_db.in_session
    @mock.patch.object(client.OpenDaylightRestClient, 'sendjson',
                       mock.Mock(side_effect=Exception))
    def test__sync_entry_update_state_by_retry_count_on_exception(self):
        entry = db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        self.journal._max_retry_count = 1
        self.assertEqual(entry.retry_count, 0)
        self.journal._sync_entry(self.db_context, entry)
        self.assertEqual(entry.retry_count, 1)
        self.assertEqual(entry.state, odl_const.PENDING)
        self.journal._sync_entry(self.db_context, entry)
        self.assertEqual(entry.retry_count, 1)
        self.assertEqual(entry.state, odl_const.FAILED)

    def _test__sync_entry_logs(self, log_type):
        entry = db.create_pending_row(self.db_context, *self.UPDATE_ROW)
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

    @mock.patch.object(journal.OpenDaylightJournalThread,
                       'sync_pending_entries')
    def test_terminate_journal_thread_correctly(self, mock_journal):
        self.journal_thread_fixture.journal_thread_mock.stop()
        self.addCleanup(self.journal_thread_fixture.journal_thread_mock.start)

        journal_thread = journal.OpenDaylightJournalThread(start_thread=True)

        journal_thread.stop(5)
        self.assertTrue(not journal_thread._odl_sync_thread.is_alive())
        mock_journal.assert_called_once()

    @mock.patch.object(journal.OpenDaylightJournalThread,
                       'sync_pending_entries')
    def test_allow_multiple_starts_gracefully(self, mock_journal):
        self.journal_thread_fixture.journal_thread_mock.stop()
        self.addCleanup(self.journal_thread_fixture.journal_thread_mock.start)
        journal_thread = journal.OpenDaylightJournalThread(start_thread=False)
        self.addCleanup(journal_thread.stop)
        journal_thread.start()

        try:
            journal_thread.start()
        except RuntimeError:
            self.fail('OpenDaylightJournalThread started twice')


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
            self._test_retry_exceptions(journal.entry_complete, m)

    @test_db.in_session
    def _test_entry_complete(self, retention, expected_length):
        self.cfg.config(completed_rows_retention=retention, group='ml2_odl')
        db.create_pending_row(self.db_context, *test_db.DbTestCase.UPDATE_ROW)
        entry = db.get_all_db_rows(self.db_context)[-1]
        journal.entry_complete(self.db_context, entry)
        rows = db.get_all_db_rows(self.db_context)
        self.assertEqual(expected_length, len(rows))
        self.assertTrue(
            all(row.state == odl_const.COMPLETED for row in rows))

    def test_entry_complete_no_retention(self):
        self._test_entry_complete(0, 0)

    def test_entry_complete_with_retention(self):
        self._test_entry_complete(1, 1)

    def test_entry_complete_with_indefinite_retention(self):
        self._test_entry_complete(-1, 1)

    @test_db.in_session
    def test_entry_complete_with_retention_deletes_dependencies(self):
        self.cfg.config(completed_rows_retention=1, group='ml2_odl')
        db.create_pending_row(self.db_context, *test_db.DbTestCase.UPDATE_ROW)
        entry = db.get_all_db_rows(self.db_context)[-1]
        db.create_pending_row(self.db_context, *test_db.DbTestCase.UPDATE_ROW,
                              depending_on=[entry])
        dependant = db.get_all_db_rows(self.db_context)[-1]
        journal.entry_complete(self.db_context, entry)
        rows = db.get_all_db_rows(self.db_context)
        self.assertIn(entry, rows)
        self.assertEqual([], entry.dependencies)
        self.assertEqual([], dependant.depending_on)

    def test_entry_reset_retries_exceptions(self):
        with mock.patch.object(db, 'update_db_row_state') as m:
            self._test_retry_exceptions(journal.entry_reset, m)

    @test_db.in_session
    def test_entry_reset(self):
        db.create_pending_row(self.db_context, *test_db.DbTestCase.UPDATE_ROW)
        db.create_pending_row(self.db_context, *test_db.DbTestCase.UPDATE_ROW)
        entry = db.get_all_db_rows(self.db_context)[-1]
        entry.state = odl_const.PROCESSING
        self.db_context.session.merge(entry)
        self.db_context.session.flush()
        entry = db.get_all_db_rows(self.db_context)[-1]
        self.assertEqual(entry.state, odl_const.PROCESSING)
        journal.entry_reset(self.db_context, entry)
        rows = db.get_all_db_rows(self.db_context)
        self.assertEqual(2, len(rows))
        self.assertTrue(all(row.state == odl_const.PENDING for row in rows))

    def test_entry_set_retry_count_retries_exceptions(self):
        with mock.patch.object(db, 'update_pending_db_row_retry') as m:
            self._test_retry_exceptions(
                journal.entry_update_state_by_retry_count, m)

    @test_db.in_session
    def test_entry_set_retry_count(self):
        db.create_pending_row(self.db_context, *test_db.DbTestCase.UPDATE_ROW)
        entry_baseline = db.get_all_db_rows(self.db_context)[-1]
        db.create_pending_row(self.db_context, *test_db.DbTestCase.UPDATE_ROW)
        entry_target = db.get_all_db_rows(self.db_context)[-1]
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
        entry = db.create_pending_row(self.db_context, *self.UPDATE_ROW)

        logger = self.useFixture(fixtures.FakeLogger(level=logging.DEBUG))
        journal.record(self.db_context, *self.UPDATE_ROW)
        self.assertIn(str(entry.seqnum), logger.output)
