# Copyright (c) 2015 OpenStack Foundation
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
import datetime

from neutron.db import api as db_api
from neutron_lib.db import api as lib_db_api
from oslo_log import log as logging
from sqlalchemy import asc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from networking_odl.common import constants as odl_const
from networking_odl.db import models

LOG = logging.getLogger(__name__)


def get_pending_or_processing_ops(context, object_uuid, operation=None):
    q = context.session.query(models.OpenDaylightJournal).filter(
        or_(models.OpenDaylightJournal.state == odl_const.PENDING,
            models.OpenDaylightJournal.state == odl_const.PROCESSING),
        models.OpenDaylightJournal.object_uuid == object_uuid)

    if operation:
        if isinstance(operation, (list, tuple)):
            q = q.filter(models.OpenDaylightJournal.operation.in_(operation))
        else:
            q = q.filter(models.OpenDaylightJournal.operation == operation)

    return q.all()


def get_pending_delete_ops_with_parent(context, object_type, parent_id):
    rows = context.session.query(models.OpenDaylightJournal).filter(
        or_(models.OpenDaylightJournal.state == odl_const.PENDING,
            models.OpenDaylightJournal.state == odl_const.PROCESSING),
        models.OpenDaylightJournal.object_type == object_type,
        models.OpenDaylightJournal.operation == odl_const.ODL_DELETE
    ).all()

    return (row for row in rows if parent_id in row.data)


def get_all_db_rows(context):
    return context.session.query(models.OpenDaylightJournal).all()


def get_all_db_rows_by_state(context, state):
    return context.session.query(models.OpenDaylightJournal).filter_by(
        state=state).all()


# Retry deadlock exception for Galera DB.
# If two (or more) different threads call this method at the same time, they
# might both succeed in changing the same row to pending, but at least one
# of them will get a deadlock from Galera and will have to retry the operation.
@lib_db_api.retry_if_session_inactive()
@db_api.context_manager.writer.savepoint
def get_oldest_pending_db_row_with_lock(context):
    journal_dep = aliased(models.OpenDaylightJournal)
    dep_query = context.session.query(journal_dep).filter(
        models.OpenDaylightJournal.seqnum == journal_dep.seqnum
    ).outerjoin(
        journal_dep.depending_on, aliased=True).filter(
        or_(models.OpenDaylightJournal.state == odl_const.PENDING,
            models.OpenDaylightJournal.state == odl_const.PROCESSING))
    row = context.session.query(models.OpenDaylightJournal).filter(
        models.OpenDaylightJournal.state == odl_const.PENDING,
        ~ dep_query.exists()
    ).order_by(
        asc(models.OpenDaylightJournal.last_retried)).first()
    if row:
        update_db_row_state(context, row, odl_const.PROCESSING)

    return row


def delete_dependency(context, entry):
    """Delete dependency upon the given ID"""
    conn = context.session.connection()
    stmt = models.journal_dependencies.delete(
        models.journal_dependencies.c.depends_on == entry.seqnum)
    conn.execute(stmt)
    context.session.expire_all()


def update_db_row_state(context, row, state, flush=True):
    row.state = state
    context.session.merge(row)
    if flush:
        context.session.flush()


def update_pending_db_row_retry(context, row, retry_count):
    if row.retry_count >= retry_count:
        update_db_row_state(context, row, odl_const.FAILED)
    else:
        row.retry_count += 1
        update_db_row_state(context, row, odl_const.PENDING)


def delete_row(context, row=None, row_id=None, flush=True):
    if row_id:
        row = context.session.query(models.OpenDaylightJournal).filter_by(
            seqnum=row_id).one()
    if row:
        context.session.delete(row)
        if flush:
            context.session.flush()


def create_pending_row(context, object_type, object_uuid,
                       operation, data, depending_on=None):
    if depending_on is None:
        depending_on = []
    row = models.OpenDaylightJournal(object_type=object_type,
                                     object_uuid=object_uuid,
                                     operation=operation, data=data,
                                     state=odl_const.PENDING,
                                     depending_on=depending_on)
    context.session.add(row)
    # Keep session flush for unit tests. NOOP for L2/L3 events since calls are
    # made inside database session transaction with subtransactions=True.
    context.session.flush()
    return row


@db_api.context_manager.writer.savepoint
def delete_pending_rows(context, operations_to_delete):
    context.session.query(models.OpenDaylightJournal).filter(
        models.OpenDaylightJournal.operation.in_(operations_to_delete),
        models.OpenDaylightJournal.state == odl_const.PENDING).delete(
        synchronize_session=False)
    context.session.expire_all()


def _update_periodic_task_state(context, expected_state, state, task):
    row = context.session.query(models.OpenDaylightPeriodicTask).filter_by(
        state=expected_state,
        task=task).with_for_update().one_or_none()

    if row is None:
        return False

    row.state = state
    return True


def was_periodic_task_executed_recently(context, task, interval):
    now = context.session.execute(func.now()).scalar()
    delta = datetime.timedelta(seconds=interval)
    row = context.session.query(models.OpenDaylightPeriodicTask).filter(
        models.OpenDaylightPeriodicTask.task == task,
        (now - delta >= (models.OpenDaylightPeriodicTask.lock_updated))
    ).one_or_none()

    return bool(row is None)


def lock_periodic_task(context, task):
    return _update_periodic_task_state(context, odl_const.PENDING,
                                       odl_const.PROCESSING, task)


def unlock_periodic_task(context, task):
    return _update_periodic_task_state(context, odl_const.PROCESSING,
                                       odl_const.PENDING, task)


def update_periodic_task(context, task, operation=None):
    """Update the current periodic task details.

    The function assumes the lock is held, so it mustn't be run outside of a
    locked context.
    """
    op_text = None
    if operation:
        op_text = operation.__name__

    row = context.session.query(models.OpenDaylightPeriodicTask).filter_by(
        task=task).one()
    row.processing_operation = op_text


@db_api.context_manager.writer.savepoint
def delete_rows_by_state_and_time(context, state, time_delta):
    # NOTE(mpeterson): The reason behind deleting one-by-one is that InnoDB
    # ignores the WHERE clause to issue a LOCK when executing a DELETE. By
    # executing each operation indepently, we minimize exposures to DEADLOCKS.
    now = context.session.execute(func.now()).scalar()
    rows = context.session.query(models.OpenDaylightJournal).filter(
        models.OpenDaylightJournal.state == state,
        models.OpenDaylightJournal.last_retried < now - time_delta).all()
    for row in rows:
        delete_row(context, row, flush=False)
    context.session.expire_all()


@db_api.context_manager.writer.savepoint
def reset_processing_rows(context, max_timedelta):
    # NOTE(mpeterson): The reason behind updating one-by-one is that InnoDB
    # ignores the WHERE clause to issue a LOCK when executing an UPDATE. By
    # executing each operation indepently, we minimize exposures to DEADLOCKS.
    now = context.session.execute(func.now()).scalar()
    max_timedelta = datetime.timedelta(seconds=max_timedelta)
    rows = context.session.query(models.OpenDaylightJournal).filter(
        models.OpenDaylightJournal.last_retried < now - max_timedelta,
        models.OpenDaylightJournal.state == odl_const.PROCESSING).all()
    for row in rows:
        update_db_row_state(context, row, odl_const.PENDING, flush=False)

    return len(rows)
