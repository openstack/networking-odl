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

from sqlalchemy import asc
from sqlalchemy import bindparam
from sqlalchemy.ext import baked
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from oslo_log import log as logging

from neutron.db import api as db_api

from networking_odl.common import constants as odl_const
from networking_odl.db import models

LOG = logging.getLogger(__name__)

bakery = baked.bakery()


def get_pending_or_processing_ops(session, object_uuid, operation=None):
    # NOTE (sai): For performance reasons, we expect this method to use baked
    # query (http://docs.sqlalchemy.org/en/latest/orm/extensions/baked.html)
    baked_query = bakery(lambda s: s.query(
        models.OpenDaylightJournal))
    baked_query += lambda q: q.filter(
        or_(models.OpenDaylightJournal.state == odl_const.PENDING,
            models.OpenDaylightJournal.state == odl_const.PROCESSING),
        models.OpenDaylightJournal.object_uuid == bindparam('uuid'))
    if operation:
        if isinstance(operation, (list, tuple)):
            baked_query += lambda q: q.filter(
                models.OpenDaylightJournal.operation.in_(bindparam('op',
                                                         expanding=True)))
        else:
            baked_query += lambda q: q.filter(
                models.OpenDaylightJournal.operation == bindparam('op'))

    return baked_query(session).params(
        uuid=object_uuid, op=operation).all()


def get_pending_delete_ops_with_parent(session, object_type, parent_id):
    rows = session.query(models.OpenDaylightJournal).filter(
        or_(models.OpenDaylightJournal.state == odl_const.PENDING,
            models.OpenDaylightJournal.state == odl_const.PROCESSING),
        models.OpenDaylightJournal.object_type == object_type,
        models.OpenDaylightJournal.operation == odl_const.ODL_DELETE
    ).all()

    return (row for row in rows if parent_id in row.data)


def get_all_db_rows(session):
    return session.query(models.OpenDaylightJournal).all()


def get_all_db_rows_by_state(session, state):
    return session.query(models.OpenDaylightJournal).filter_by(
        state=state).all()


# Retry deadlock exception for Galera DB.
# If two (or more) different threads call this method at the same time, they
# might both succeed in changing the same row to pending, but at least one
# of them will get a deadlock from Galera and will have to retry the operation.
@db_api.retry_db_errors
def get_oldest_pending_db_row_with_lock(session):
    # NOTE (sai): For performance reasons, we expect this method to use baked
    # query (http://docs.sqlalchemy.org/en/latest/orm/extensions/baked.html)
    with db_api.autonested_transaction(session):
        journal_dep = aliased(models.OpenDaylightJournal)
        dep_query = bakery(lambda s1: s1.query(journal_dep))
        dep_query += lambda q: q.filter(
            models.OpenDaylightJournal.seqnum == journal_dep.seqnum)
        dep_query += lambda q: q.outerjoin(
            journal_dep.depending_on, aliased=True)
        dep_query += lambda q: q.filter(
            or_(models.OpenDaylightJournal.state == odl_const.PENDING,
                models.OpenDaylightJournal.state == odl_const.PROCESSING))
        row = bakery(lambda s2: s2.query(models.OpenDaylightJournal))
        row += lambda q: q.filter(
            models.OpenDaylightJournal.state == odl_const.PENDING,
            ~ (dep_query._as_query(q.session)).exists())
        row += lambda q: q.order_by(
            asc(models.OpenDaylightJournal.last_retried))
        row = row(session).first()
        if row:
            update_db_row_state(session, row, odl_const.PROCESSING)

    return row


def delete_dependency(session, entry):
    """Delete dependency upon the given ID"""
    conn = session.connection()
    stmt = models.journal_dependencies.delete(
        models.journal_dependencies.c.depends_on == entry.seqnum)
    conn.execute(stmt)
    session.expire_all()


def update_db_row_state(session, row, state, flush=True):
    row.state = state
    session.merge(row)
    if flush:
        session.flush()


def update_pending_db_row_retry(session, row, retry_count):
    if row.retry_count >= retry_count:
        update_db_row_state(session, row, odl_const.FAILED)
    else:
        row.retry_count += 1
        update_db_row_state(session, row, odl_const.PENDING)


def delete_row(session, row=None, row_id=None, flush=True):
    if row_id:
        row = session.query(models.OpenDaylightJournal).filter_by(
            seqnum=row_id).one()
    if row:
        session.delete(row)
        if flush:
            session.flush()


def create_pending_row(session, object_type, object_uuid,
                       operation, data, depending_on=None):
    if depending_on is None:
        depending_on = []
    row = models.OpenDaylightJournal(object_type=object_type,
                                     object_uuid=object_uuid,
                                     operation=operation, data=data,
                                     state=odl_const.PENDING,
                                     depending_on=depending_on)
    session.add(row)
    # Keep session flush for unit tests. NOOP for L2/L3 events since calls are
    # made inside database session transaction with subtransactions=True.
    session.flush()
    return row


def delete_pending_rows(session, operations_to_delete):
    with db_api.autonested_transaction(session):
        session.query(models.OpenDaylightJournal).filter(
            models.OpenDaylightJournal.operation.in_(operations_to_delete),
            models.OpenDaylightJournal.state == odl_const.PENDING).delete(
            synchronize_session=False)
        session.expire_all()


def _update_periodic_task_state(session, expected_state, state, task):
    row = session.query(models.OpenDaylightPeriodicTask).filter_by(
        state=expected_state,
        task=task).with_for_update().one_or_none()

    if row is None:
        return False

    row.state = state
    return True


def was_periodic_task_executed_recently(session, task, interval):
    now = session.execute(func.now()).scalar()
    delta = datetime.timedelta(seconds=interval)
    row = session.query(models.OpenDaylightPeriodicTask).filter(
        models.OpenDaylightPeriodicTask.task == task,
        (now - delta >= (models.OpenDaylightPeriodicTask.lock_updated))
    ).one_or_none()

    return bool(row is None)


def lock_periodic_task(session, task):
    return _update_periodic_task_state(session, odl_const.PENDING,
                                       odl_const.PROCESSING, task)


def unlock_periodic_task(session, task):
    return _update_periodic_task_state(session, odl_const.PROCESSING,
                                       odl_const.PENDING, task)


def update_periodic_task(session, task, operation=None):
    """Update the current periodic task details.

    The function assumes the lock is held, so it mustn't be run outside of a
    locked context.
    """
    op_text = None
    if operation:
        op_text = operation.__name__

    row = session.query(models.OpenDaylightPeriodicTask).filter_by(
        task=task).one()
    row.processing_operation = op_text


def delete_rows_by_state_and_time(session, state, time_delta):
    # NOTE(mpeterson): The reason behind deleting one-by-one is that InnoDB
    # ignores the WHERE clause to issue a LOCK when executing a DELETE. By
    # executing each operation indepently, we minimize exposures to DEADLOCKS.
    with db_api.autonested_transaction(session):
        now = session.execute(func.now()).scalar()
        rows = session.query(models.OpenDaylightJournal).filter(
            models.OpenDaylightJournal.state == state,
            models.OpenDaylightJournal.last_retried < now - time_delta).all()
        for row in rows:
            delete_row(session, row, flush=False)
        session.expire_all()


def reset_processing_rows(session, max_timedelta):
    # NOTE(mpeterson): The reason behind updating one-by-one is that InnoDB
    # ignores the WHERE clause to issue a LOCK when executing an UPDATE. By
    # executing each operation indepently, we minimize exposures to DEADLOCKS.
    with db_api.autonested_transaction(session):
        now = session.execute(func.now()).scalar()
        max_timedelta = datetime.timedelta(seconds=max_timedelta)
        rows = session.query(models.OpenDaylightJournal).filter(
            models.OpenDaylightJournal.last_retried < now - max_timedelta,
            models.OpenDaylightJournal.state == odl_const.PROCESSING).all()
        for row in rows:
            update_db_row_state(session, row, odl_const.PENDING, flush=False)

    return len(rows)
