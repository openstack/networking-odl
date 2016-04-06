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
from sqlalchemy import asc
from sqlalchemy import func
from sqlalchemy import or_

from networking_odl.common import constants as odl_const
from networking_odl.db import models

from neutron.db import api as db_api

from oslo_db import api as oslo_db_api


def check_for_pending_or_processing_ops(session, object_uuid, operation=None):
    q = session.query(models.OpendaylightJournal).filter(
        or_(models.OpendaylightJournal.state == odl_const.PENDING,
            models.OpendaylightJournal.state == odl_const.PROCESSING),
        models.OpendaylightJournal.object_uuid == object_uuid)
    if operation:
        if isinstance(operation, (list, tuple)):
            q = q.filter(models.OpendaylightJournal.operation.in_(operation))
        else:
            q = q.filter(models.OpendaylightJournal.operation == operation)
    return session.query(q.exists()).scalar()


def check_for_pending_delete_ops_with_parent(session, object_type, parent_id):
    rows = session.query(models.OpendaylightJournal).filter(
        or_(models.OpendaylightJournal.state == odl_const.PENDING,
            models.OpendaylightJournal.state == odl_const.PROCESSING),
        models.OpendaylightJournal.object_type == object_type,
        models.OpendaylightJournal.operation == odl_const.ODL_DELETE
    ).all()

    for row in rows:
        if parent_id in row.data:
            return True

    return False


def check_for_pending_or_processing_add(session, router_id, subnet_id):
    rows = session.query(models.OpendaylightJournal).filter(
        or_(models.OpendaylightJournal.state == odl_const.PENDING,
            models.OpendaylightJournal.state == odl_const.PROCESSING),
        models.OpendaylightJournal.object_type == odl_const.ODL_ROUTER_INTF,
        models.OpendaylightJournal.operation == odl_const.ODL_ADD
    ).all()

    for row in rows:
        if router_id in row.data.values() and subnet_id in row.data.values():
            return True

    return False


def check_for_pending_remove_ops_with_parent(session, parent_id):
    rows = session.query(models.OpendaylightJournal).filter(
        or_(models.OpendaylightJournal.state == odl_const.PENDING,
            models.OpendaylightJournal.state == odl_const.PROCESSING),
        models.OpendaylightJournal.object_type == odl_const.ODL_ROUTER_INTF,
        models.OpendaylightJournal.operation == odl_const.ODL_REMOVE
    ).all()

    for row in rows:
        if parent_id in row.data.values():
            return True

    return False


def check_for_older_ops(session, row):
    q = session.query(models.OpendaylightJournal).filter(
        or_(models.OpendaylightJournal.state == odl_const.PENDING,
            models.OpendaylightJournal.state == odl_const.PROCESSING),
        models.OpendaylightJournal.operation == row.operation,
        models.OpendaylightJournal.object_uuid == row.object_uuid,
        models.OpendaylightJournal.created_at < row.created_at,
        models.OpendaylightJournal.id != row.id)
    return session.query(q.exists()).scalar()


def get_all_db_rows(session):
    return session.query(models.OpendaylightJournal).all()


def get_all_db_rows_by_state(session, state):
    return session.query(models.OpendaylightJournal).filter_by(
        state=state).all()


# Retry deadlock exception for Galera DB.
# If two (or more) different threads call this method at the same time, they
# might both succeed in changing the same row to pending, but at least one
# of them will get a deadlock from Galera and will have to retry the operation.
@db_api.retry_db_errors
def get_oldest_pending_db_row_with_lock(session):
    with session.begin():
        row = session.query(models.OpendaylightJournal).filter_by(
            state=odl_const.PENDING).order_by(
            asc(models.OpendaylightJournal.last_retried)).with_for_update(
        ).first()
        if row:
            update_db_row_state(session, row, odl_const.PROCESSING)

    return row


@oslo_db_api.wrap_db_retry(max_retries=db_api.MAX_RETRIES,
                           retry_on_request=True)
def update_db_row_state(session, row, state):
    row.state = state
    session.merge(row)
    session.flush()


def update_pending_db_row_retry(session, row, retry_count):
    if row.retry_count >= retry_count:
        update_db_row_state(session, row, odl_const.FAILED)
    else:
        row.retry_count += 1
        update_db_row_state(session, row, odl_const.PENDING)


# This function is currently not used.
# Deleted resources are marked as 'deleted' in the database.
@oslo_db_api.wrap_db_retry(max_retries=db_api.MAX_RETRIES,
                           retry_on_request=True)
def delete_row(session, row=None, row_id=None):
    if row_id:
        row = session.query(models.OpendaylightJournal).filter_by(
            id=row_id).one()
    if row:
        session.delete(row)
        session.flush()


@oslo_db_api.wrap_db_retry(max_retries=db_api.MAX_RETRIES,
                           retry_on_request=True)
def create_pending_row(session, object_type, object_uuid,
                       operation, data):
    row = models.OpendaylightJournal(object_type=object_type,
                                     object_uuid=object_uuid,
                                     operation=operation, data=data,
                                     created_at=func.now(),
                                     state=odl_const.PENDING)
    session.add(row)
    # Keep session flush for unit tests. NOOP for L2/L3 events since calls are
    # made inside database session transaction with subtransactions=True.
    session.flush()
