#
# Copyright (C) 2016 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#

import threading

import mock
from neutron.common import utils
from neutron_lib import context

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.db import models
from networking_odl.journal import periodic_task
from networking_odl.tests.unit import test_base_db


TEST_TASK_NAME = 'test-maintenance'
TEST_TASK_INTERVAL = 0.1


class PeriodicTaskThreadTestCase(test_base_db.ODLBaseDbTestCase):
    def setUp(self):
        super(PeriodicTaskThreadTestCase, self).setUp()
        row = models.OpenDaylightPeriodicTask(task=TEST_TASK_NAME,
                                              state=odl_const.PENDING)
        self.db_context.session.add(row)
        self.db_context.session.flush()

        self.thread = periodic_task.PeriodicTask(TEST_TASK_NAME,
                                                 TEST_TASK_INTERVAL)
        self.addCleanup(self.thread.cleanup)

    def test__execute_op_no_exception(self):
        with mock.patch.object(periodic_task, 'LOG') as mock_log:
            operation = mock.MagicMock()
            operation.__name__ = "test"
            self.thread.register_operation(operation)
            self.thread._execute_op(operation, self.db_context)
            operation.assert_called()
            mock_log.info.assert_called()
            mock_log.exception.assert_not_called()

    def test__execute_op_with_exception(self):
        with mock.patch.object(periodic_task, 'LOG') as mock_log:
            operation = mock.MagicMock(side_effect=Exception())
            operation.__name__ = "test"
            self.thread._execute_op(operation, self.db_context)
            mock_log.exception.assert_called()

    def test_thread_works(self):
        callback_event = threading.Event()
        # TODO(mpeterson): Make this an int when Py2 is no longer supported
        # and use the `nonlocal` directive
        count = [0]

        def callback_op(*args):
            count[0] += 1

            # The following should be true on the second call, so we're making
            # sure that the thread runs more than once.
            if count[0] > 1:
                callback_event.set()

        self.thread.register_operation(callback_op)
        self.thread.start()

        # Make sure the callback event was called and not timed out
        self.assertTrue(callback_event.wait(timeout=5))

    def test_thread_continues_after_exception(self):
        exception_event = threading.Event()
        callback_event = threading.Event()

        def exception_op(*args):
            if not exception_event.is_set():
                exception_event.set()
                raise Exception()

        def callback_op(*args):
            callback_event.set()

        for op in [exception_op, callback_op]:
            self.thread.register_operation(op)

        self.thread.start()

        # Make sure the callback event was called and not timed out
        self.assertTrue(callback_event.wait(timeout=5))

    def test_multiple_thread_work(self):
        self.thread1 = periodic_task.PeriodicTask(TEST_TASK_NAME + '1',
                                                  TEST_TASK_INTERVAL)
        callback_event = threading.Event()
        callback_event1 = threading.Event()
        self.addCleanup(self.thread1.cleanup)

        def callback_op(*args):
            callback_event.set()

        def callback_op1(*args):
            callback_event1.set()

        self.thread.register_operation(callback_op)
        self.thread.register_operation(callback_op1)
        self.thread.start()
        self.assertTrue(callback_event.wait(timeout=5))

        self.thread1.start()
        self.assertTrue(callback_event1.wait(timeout=5))

    @mock.patch.object(db, "was_periodic_task_executed_recently")
    def test_back_to_back_job(self, mock_status_method):
        callback_event = threading.Event()
        continue_event = threading.Event()

        def callback_op(*args):
            callback_event.set()

        return_value = True

        def continue_(*args, **kwargs):
            continue_event.set()
            return return_value
        mock_status_method.side_effect = continue_

        self.thread.register_operation(callback_op)
        msg = ("Periodic %s task executed after periodic "
               "interval Skipping execution.")
        with mock.patch.object(periodic_task.LOG, 'info') as mock_log_info:
            self.thread.start()
            self.assertTrue(continue_event.wait(timeout=1))
            continue_event.clear()
            mock_log_info.assert_called_with(msg, TEST_TASK_NAME)
            self.assertFalse(callback_event.is_set())
            self.assertTrue(continue_event.wait(timeout=1))
            continue_event.clear()
            mock_log_info.assert_called_with(msg, TEST_TASK_NAME)
            return_value = False
            self.assertTrue(callback_event.wait(timeout=2))

    def test_set_operation_retries_exceptions(self):
        with mock.patch.object(db, 'update_periodic_task') as m:
            self._test_retry_exceptions(self.thread._set_operation, m)

    def test_lock_task_retries_exceptions(self):
        with mock.patch.object(db, 'lock_periodic_task') as m:
            self._test_retry_exceptions(self.thread._lock_task, m)

    def test_clear_and_unlock_task_retries_exceptions(self):
        with mock.patch.object(db, 'update_periodic_task') as m:
            self._test_retry_exceptions(self.thread._clear_and_unlock_task, m)

    @mock.patch.object(db, "was_periodic_task_executed_recently",
                       return_value=False)
    def test_no_multiple_executions_simultaneously(self, mock_exec_recently):
        continue_event = threading.Event()
        trigger_event = threading.Event()
        # TODO(mpeterson): Make this an int when Py2 is no longer supported
        # and use the `nonlocal` directive
        count = [0]

        def wait_until_event(context):
            trigger_event.set()
            if continue_event.wait(2):
                count[0] += 1

        self.thread.register_operation(wait_until_event)

        def task_locked():
            session = self.db_context.session
            row = (session.query(models.OpenDaylightPeriodicTask)
                          .filter_by(state=odl_const.PROCESSING,
                                     task=TEST_TASK_NAME)
                          .one_or_none())
            return (row is not None)

        self.thread.start()
        utils.wait_until_true(trigger_event.is_set, 5, 0.01)
        self.assertEqual(count[0], 0)
        self.assertTrue(task_locked())

        self.thread.execute_ops()
        self.assertEqual(count[0], 0)
        self.assertTrue(task_locked())

        continue_event.set()
        trigger_event.clear()
        utils.wait_until_true(trigger_event.is_set, 5, 0.01)
        self.thread.cleanup()
        self.assertFalse(task_locked())
        self.assertGreaterEqual(count[0], 1)

    @mock.patch.object(db, "was_periodic_task_executed_recently",
                       return_value=True)
    def test_forced_execution(self, mock_status_method):
        operation = mock.MagicMock()
        operation.__name__ = "test"
        self.thread.register_operation(operation)

        self.thread.execute_ops(forced=True)

        operation.assert_called()

    @mock.patch.object(db, "was_periodic_task_executed_recently",
                       return_value=True)
    def test_context_is_passed_as_args(self, _):
        operation = mock.MagicMock()
        operation.__name__ = 'test'
        self.thread.register_operation(operation)

        self.thread.execute_ops(forced=True)

        # This tests that only ONE args is passed, and no kwargs
        operation.assert_called_with(mock.ANY)

        # This tests that it's a context
        kall = operation.call_args
        args, kwargs = kall
        self.assertIsInstance(args[0], context.Context)
