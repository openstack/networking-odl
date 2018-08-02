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

from datetime import timedelta
import functools

import mock

from neutron.db import api as db_api
from neutron_lib.db import api as lib_db_api

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.db import models
from networking_odl.tests.unit import test_base_db


def in_session(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with db_api.context_manager.writer.using(self.db_context):
            return fn(self, *args, **kwargs)
    return wrapper


class DbTestCase(test_base_db.ODLBaseDbTestCase):
    def setUp(self):
        super(DbTestCase, self).setUp()
        # NOTE(mpeterson): Due to how the pecan lib does introspection
        # to find a non-decorated function, it needs a function that will
        # be found in the end. The line below workarounds this limitation.
        self._mock_function = mock.MagicMock()

    def _update_row(self, row):
        self.db_context.session.merge(row)
        self.db_context.session.flush()

    def _test_validate_updates(self, first_entry, second_entry, expected_deps,
                               state=None):
        db.create_pending_row(self.db_context, *first_entry)
        if state:
            row = db.get_all_db_rows(self.db_context)[0]
            row.state = state
            self._update_row(row)

        deps = db.get_pending_or_processing_ops(
            self.db_context, second_entry[1], second_entry[2])
        self.assertEqual(expected_deps, len(deps) != 0)

    def _test_retry_count(self, retry_num, max_retry,
                          expected_retry_count, expected_state):
        # add new pending row
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)

        # update the row with the requested retry_num
        row = db.get_all_db_rows(self.db_context)[0]
        row.retry_count = retry_num - 1
        db.update_pending_db_row_retry(self.db_context, row, max_retry)

        # validate the state and the retry_count of the row
        row = db.get_all_db_rows(self.db_context)[0]
        self.assertEqual(expected_state, row.state)
        self.assertEqual(expected_retry_count, row.retry_count)

    def _test_retry_wrapper(self, decorated_function):
        # NOTE(mpeterson): we want to make sure that it's configured
        # to MAX_RETRIES.
        self.assertEqual(lib_db_api._retry_db_errors.max_retries,
                         lib_db_api.MAX_RETRIES)

        self._test_retry_exceptions(decorated_function,
                                    self._mock_function, False)

    # NOTE(mpeterson): The following function serves to workaround a
    # limitation in the discovery mechanism of pecan lib that does not allow
    # us to create a generic function that decorates on the fly. It needs to
    # be decorated through the decorator directive and not via function
    # composition
    @lib_db_api.retry_if_session_inactive()
    def _decorated_retry_if_session_inactive(self, context):
        self._mock_function()

    def test_retry_if_session_inactive(self):
        self._test_retry_wrapper(self._decorated_retry_if_session_inactive)

    @in_session
    def _test_update_row_state(self, from_state, to_state, dry_flush=False):
        # add new pending row
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)

        mock_flush = mock.MagicMock(
            side_effect=self.db_context.session.flush)

        if dry_flush:
            patch_flush = mock.patch.object(self.db_context.session,
                                            'flush',
                                            side_effect=mock_flush)

        row = db.get_all_db_rows(self.db_context)[0]
        for state in [from_state, to_state]:
            if dry_flush:
                patch_flush.start()

            try:
                # update the row state
                db.update_db_row_state(self.db_context, row, state,
                                       flush=not dry_flush)
            finally:
                if dry_flush:
                    patch_flush.stop()

            # validate the new state
            row = db.get_all_db_rows(self.db_context)[0]
            self.assertEqual(state, row.state)

        return mock_flush

    def test_updates_same_object_uuid(self):
        self._test_validate_updates(self.UPDATE_ROW, self.UPDATE_ROW, True)

    def test_validate_updates_different_object_uuid(self):
        other_row = list(self.UPDATE_ROW)
        other_row[1] += 'a'
        self._test_validate_updates(self.UPDATE_ROW, other_row, False)

    def test_validate_updates_different_object_type(self):
        other_row = list(self.UPDATE_ROW)
        other_row[0] = odl_const.ODL_PORT
        other_row[1] += 'a'
        self._test_validate_updates(self.UPDATE_ROW, other_row, False)

    def test_check_for_older_ops_processing(self):
        self._test_validate_updates(self.UPDATE_ROW, self.UPDATE_ROW, True,
                                    state=odl_const.PROCESSING)

    @in_session
    def test_get_oldest_pending_row_none_when_no_rows(self):
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        self.assertIsNone(row)

    @in_session
    def _test_get_oldest_pending_row_none(self, state):
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        row = db.get_all_db_rows(self.db_context)[0]
        row.state = state
        self._update_row(row)

        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        self.assertIsNone(row)

    def test_get_oldest_pending_row_none_when_row_processing(self):
        self._test_get_oldest_pending_row_none(odl_const.PROCESSING)

    def test_get_oldest_pending_row_none_when_row_failed(self):
        self._test_get_oldest_pending_row_none(odl_const.FAILED)

    def test_get_oldest_pending_row_none_when_row_completed(self):
        self._test_get_oldest_pending_row_none(odl_const.COMPLETED)

    def test_get_oldest_pending_row(self):
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        self.assertIsNotNone(row)
        self.assertEqual(odl_const.PROCESSING, row.state)

    @in_session
    def test_get_oldest_pending_row_order(self):
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        older_row = db.get_all_db_rows(self.db_context)[0]
        older_row.last_retried -= timedelta(minutes=1)
        self._update_row(older_row)

        db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        self.assertEqual(older_row, row)

    def _test_get_oldest_pending_row_with_dep(self, dep_state):
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        parent_row = db.get_all_db_rows(self.db_context)[0]
        db.update_db_row_state(self.db_context, parent_row, dep_state)
        db.create_pending_row(self.db_context, *self.UPDATE_ROW,
                              depending_on=[parent_row])
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        if row is not None:
            self.assertNotEqual(parent_row.seqnum, row.seqnum)

        return row

    def test_get_oldest_pending_row_when_dep_completed(self):
        row = self._test_get_oldest_pending_row_with_dep(odl_const.COMPLETED)
        self.assertEqual(odl_const.PROCESSING, row.state)

    def test_get_oldest_pending_row_when_dep_failed(self):
        row = self._test_get_oldest_pending_row_with_dep(odl_const.FAILED)
        self.assertEqual(odl_const.PROCESSING, row.state)

    @in_session
    def test_get_oldest_pending_row_returns_parent_when_dep_pending(self):
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        parent_row = db.get_all_db_rows(self.db_context)[0]
        db.create_pending_row(self.db_context, *self.UPDATE_ROW,
                              depending_on=[parent_row])
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        self.assertEqual(parent_row, row)

    def test_get_oldest_pending_row_none_when_dep_processing(self):
        row = self._test_get_oldest_pending_row_with_dep(odl_const.PROCESSING)
        self.assertIsNone(row)

    def test_get_oldest_pending_row_retries_exceptions(self):
        with mock.patch.object(db, 'aliased') as m:
            self._test_retry_exceptions(db.get_oldest_pending_db_row_with_lock,
                                        m)

    @in_session
    def _test_delete_row(self, by_row=False, by_row_id=False, dry_flush=False):
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)

        rows = db.get_all_db_rows(self.db_context)
        self.assertEqual(len(rows), 2)
        row = rows[-1]

        params = {'flush': not dry_flush}
        if by_row:
            params['row'] = row
        elif by_row_id:
            params['row_id'] = row.seqnum

        mock_flush = None
        if dry_flush:
            patch_flush = mock.patch.object(
                self.db_context.session, 'flush',
                side_effect=self.db_context.session.flush
            )
            mock_flush = patch_flush.start()

        try:
            db.delete_row(self.db_context, **params)
        finally:
            if dry_flush:
                patch_flush.stop()
                self.db_context.session.flush()

        rows = db.get_all_db_rows(self.db_context)
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(row.seqnum, rows[0].seqnum)

        return mock_flush

    def test_delete_row_by_row(self):
        self._test_delete_row(by_row=True)

    def test_delete_row_by_row_id(self):
        self._test_delete_row(by_row_id=True)

    def test_delete_row_by_row_without_flushing(self):
        mock_flush = self._test_delete_row(by_row=True, dry_flush=True)
        mock_flush.assert_not_called()

    def test_create_pending_row(self):
        row = db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        self.assertIsNotNone(row)
        rows = db.get_all_db_rows(self.db_context)
        self.assertTrue(row in rows)

    def _test_delete_rows_by_state_and_time(self, last_retried, row_retention,
                                            state, expected_rows,
                                            dry_delete=False):
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)

        # update state and last retried
        row = db.get_all_db_rows(self.db_context)[-1]
        row.state = state
        row.last_retried = row.last_retried - timedelta(seconds=last_retried)
        self._update_row(row)

        if not dry_delete:
            db.delete_rows_by_state_and_time(self.db_context,
                                             odl_const.COMPLETED,
                                             timedelta(seconds=row_retention))

        # validate the number of rows in the journal
        rows = db.get_all_db_rows(self.db_context)
        self.assertEqual(expected_rows, len(rows))

    def test_delete_completed_rows_no_new_rows(self):
        self._test_delete_rows_by_state_and_time(0, 10, odl_const.COMPLETED, 1)

    def test_delete_completed_rows_one_new_row(self):
        self._test_delete_rows_by_state_and_time(6, 5, odl_const.COMPLETED, 0)

    def test_delete_completed_rows_wrong_state(self):
        self._test_delete_rows_by_state_and_time(10, 8, odl_const.PENDING, 1)

    @in_session
    def test_delete_completed_rows_individually(self):
        self._test_delete_rows_by_state_and_time(
            6, 5, odl_const.COMPLETED, 1, True
        )
        patch_delete = mock.patch.object(
            self.db_context.session, 'delete',
            side_effect=self.db_context.session.delete
        )
        mock_delete = patch_delete.start()
        self.addCleanup(patch_delete.stop)
        self._test_delete_rows_by_state_and_time(
            6, 5, odl_const.COMPLETED, 0
        )
        self.assertEqual(mock_delete.call_count, 2)

    @mock.patch.object(db, 'delete_row', side_effect=db.delete_row)
    def test_delete_completed_rows_without_flush(self, mock_delete_row):
        self._test_delete_rows_by_state_and_time(6, 5, odl_const.COMPLETED, 0)
        self.assertEqual({'flush': False}, mock_delete_row.call_args[1])

    @in_session
    def _test_reset_processing_rows(self, last_retried, max_timedelta,
                                    quantity, dry_reset=False):
        db.create_pending_row(self.db_context, *self.UPDATE_ROW)
        expected_state = odl_const.PROCESSING

        row = db.get_all_db_rows(self.db_context)[-1]
        row.state = expected_state
        row.last_retried = row.last_retried - timedelta(seconds=last_retried)
        self._update_row(row)

        if not dry_reset:
            expected_state = odl_const.PENDING
            reset = db.reset_processing_rows(self.db_context, max_timedelta)
            self.assertIsInstance(reset, int)
            self.assertEqual(reset, quantity)

        rows = db.get_all_db_rows_by_state(self.db_context, expected_state)

        self.assertEqual(len(rows), quantity)
        for row in rows:
            self.assertEqual(row.state, expected_state)

    def test_reset_processing_rows(self):
        self._test_reset_processing_rows(6, 5, 1)

    def test_reset_processing_rows_no_new_rows(self):
        self._test_reset_processing_rows(0, 10, 0)

    @mock.patch.object(db, 'update_db_row_state',
                       side_effect=db.update_db_row_state)
    def test_reset_processing_rows_individually(self, mock_update_row):
        self._test_reset_processing_rows(6, 5, 1, True)
        self._test_reset_processing_rows(6, 5, 2)
        self.assertEqual(mock_update_row.call_count, 2)
        self.assertEqual(mock_update_row.call_args[1], {'flush': False})

    def test_valid_retry_count(self):
        self._test_retry_count(1, 1, 1, odl_const.PENDING)

    def test_invalid_retry_count(self):
        self._test_retry_count(2, 1, 1, odl_const.FAILED)

    def test_update_row_state_to_pending(self):
        self._test_update_row_state(odl_const.PROCESSING, odl_const.PENDING)

    def test_update_row_state_to_processing(self):
        self._test_update_row_state(odl_const.PENDING, odl_const.PROCESSING)

    def test_update_row_state_to_failed(self):
        self._test_update_row_state(odl_const.PROCESSING, odl_const.FAILED)

    def test_update_row_state_to_completed(self):
        self._test_update_row_state(odl_const.PROCESSING, odl_const.COMPLETED)

    def test_update_row_state_to_status_without_flush(self):
        mock_flush = self._test_update_row_state(odl_const.PROCESSING,
                                                 odl_const.COMPLETED,
                                                 dry_flush=True)
        # NOTE(mpeterson): call_count=2 because session.merge() calls flush()
        # and we are changing the status twice
        self.assertEqual(mock_flush.call_count, 2)

    def _test_periodic_task_lock_unlock(self, db_func, existing_state,
                                        expected_state, expected_result,
                                        task='test_task'):
        row = models.OpenDaylightPeriodicTask(state=existing_state,
                                              task=task)
        self.db_context.session.add(row)
        self.db_context.session.flush()

        self.assertEqual(expected_result, db_func(self.db_context,
                                                  task))
        row = self.db_context.session.query(
            models.OpenDaylightPeriodicTask).filter_by(task=task).one()

        self.assertEqual(expected_state, row['state'])

    def test_lock_periodic_task(self):
        self._test_periodic_task_lock_unlock(db.lock_periodic_task,
                                             odl_const.PENDING,
                                             odl_const.PROCESSING,
                                             True)

    def test_lock_periodic_task_fails_when_processing(self):
        self._test_periodic_task_lock_unlock(db.lock_periodic_task,
                                             odl_const.PROCESSING,
                                             odl_const.PROCESSING,
                                             False)

    def test_unlock_periodic_task(self):
        self._test_periodic_task_lock_unlock(db.unlock_periodic_task,
                                             odl_const.PROCESSING,
                                             odl_const.PENDING,
                                             True)

    def test_unlock_periodic_task_fails_when_pending(self):
        self._test_periodic_task_lock_unlock(db.unlock_periodic_task,
                                             odl_const.PENDING,
                                             odl_const.PENDING,
                                             False)

    def test_multiple_row_tasks(self):
        self._test_periodic_task_lock_unlock(db.unlock_periodic_task,
                                             odl_const.PENDING,
                                             odl_const.PENDING,
                                             False)

    def _add_tasks(self, tasks):
        row = []
        for count, task in enumerate(tasks):
            row.append(models.OpenDaylightPeriodicTask(state=odl_const.PENDING,
                                                       task=task))
            self.db_context.session.add(row[count])

        self.db_context.session.flush()

        rows = self.db_context.session.query(
            models.OpenDaylightPeriodicTask).all()
        self.assertEqual(len(tasks), len(rows))

    def _perform_ops_on_all_rows(self, tasks, to_lock):
        if to_lock:
            curr_state = odl_const.PENDING
            exp_state = odl_const.PROCESSING
            func = db.lock_periodic_task
        else:
            exp_state = odl_const.PENDING
            curr_state = odl_const.PROCESSING
            func = db.unlock_periodic_task

        processed = []
        for task in tasks:
            row = self.db_context.session.query(
                models.OpenDaylightPeriodicTask).filter_by(task=task).one()

            self.assertEqual(row['state'], curr_state)
            self.assertTrue(func(self.db_context, task))
            rows = self.db_context.session.query(
                models.OpenDaylightPeriodicTask).filter_by().all()

            processed.append(task)

            for row in rows:
                if row['task'] in processed:
                    self.assertEqual(exp_state, row['state'])
                else:
                    self.assertEqual(curr_state, row['state'])

        self.assertFalse(func(self.db_context, tasks[-1]))

    def test_multiple_row_tasks_lock_unlock(self):
        task1 = 'test_random_task'
        task2 = 'random_task_random'
        task3 = 'task_test_random'
        tasks = [task1, task2, task3]
        self._add_tasks(tasks)
        self._perform_ops_on_all_rows(tasks, to_lock=True)
        self._perform_ops_on_all_rows(tasks, to_lock=False)
