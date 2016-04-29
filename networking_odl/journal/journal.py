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

import copy
import threading

from requests import exceptions

from oslo_config import cfg
from oslo_log import log as logging

from neutron.db import api as neutron_db_api

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.common import filters
from networking_odl._i18n import _LI, _LE
from networking_odl.db import db
from networking_odl.journal import dependency_validations


LOG = logging.getLogger(__name__)


def call_thread_on_end(func):
    def new_func(obj, *args, **kwargs):
        return_value = func(obj, *args, **kwargs)
        obj.journal.set_sync_event()
        return return_value
    return new_func


class OpendaylightJournalThread(object):
    """Thread worker for the Opendaylight Journal Database."""
    def __init__(self):
        self.client = client.OpenDaylightRestClient.create_client()
        self._odl_sync_timeout = cfg.CONF.ml2_odl.sync_timeout
        self._row_retry_count = cfg.CONF.ml2_odl.retry_count
        self.event = threading.Event()
        self.lock = threading.Lock()
        self._odl_sync_thread = self.start_odl_sync_thread()
        self._start_sync_timer()

    def start_odl_sync_thread(self):
        # Start the sync thread
        LOG.debug("Starting a new sync thread")
        odl_sync_thread = threading.Thread(
            name='sync',
            target=self.run_sync_thread)
        odl_sync_thread.start()
        return odl_sync_thread

    def set_sync_event(self):
        # Prevent race when starting the timer
        with self.lock:
            LOG.debug("Resetting thread timer")
            self._timer.cancel()
            self._start_sync_timer()
        self.event.set()

    def _start_sync_timer(self):
        self._timer = threading.Timer(self._odl_sync_timeout,
                                      self.set_sync_event)
        self._timer.start()

    def _json_data(self, row):
        filter_cls = filters.FILTER_MAP[row.object_type]
        url_object = row.object_type.replace('_', '-')

        if row.operation == odl_const.ODL_CREATE:
            method = 'post'
            attr_filter = filter_cls.filter_create_attributes
            data = copy.deepcopy(row.data)
            urlpath = url_object + 's'
            attr_filter(data)
            to_send = {row.object_type: data}
        elif row.operation == odl_const.ODL_UPDATE:
            method = 'put'
            attr_filter = filter_cls.filter_update_attributes
            data = copy.deepcopy(row.data)
            urlpath = url_object + 's/' + row.object_uuid
            attr_filter(data)
            to_send = {row.object_type: data}
        elif row.operation == odl_const.ODL_DELETE:
            method = 'delete'
            data = None
            urlpath = url_object + 's/' + row.object_uuid
            to_send = None
        elif row.operation == odl_const.ODL_ADD:
            method = 'put'
            attr_filter = filter_cls.filter_add_attributes
            data = copy.deepcopy(row.data)
            attr_filter(data)
            urlpath = 'routers/' + data['id'] + '/add_router_interface'
            to_send = data
        elif row.operation == odl_const.ODL_REMOVE:
            method = 'put'
            attr_filter = filter_cls.filter_remove_attributes
            data = copy.deepcopy(row.data)
            attr_filter(data)
            urlpath = 'routers/' + data['id'] + '/remove_router_interface'
            to_send = data

        return method, urlpath, to_send

    def run_sync_thread(self, exit_after_run=False):
        while True:
            try:
                self.event.wait()
                self.event.clear()

                session = neutron_db_api.get_session()
                self._sync_pending_rows(session, exit_after_run)

                LOG.debug("Clearing sync thread event")
                if exit_after_run:
                    # Permanently waiting thread model breaks unit tests
                    # Adding this arg to exit here only for unit tests
                    break
            except Exception:
                # Catch exceptions to protect the thread while running
                LOG.exception(_LE("Error on run_sync_thread"))

    def _sync_pending_rows(self, session, exit_after_run):
        while True:
            LOG.debug("Thread walking database")
            row = db.get_oldest_pending_db_row_with_lock(session)
            if not row:
                LOG.debug("No rows to sync")
                break

            # Validate the operation
            validate_func = (dependency_validations.
                             VALIDATION_MAP[row.object_type])
            valid = validate_func(session, row)
            if not valid:
                LOG.info(_LI("%(operation)s %(type)s %(uuid)s is not a "
                             "valid operation yet, skipping for now"),
                         {'operation': row.operation,
                          'type': row.object_type,
                          'uuid': row.object_uuid})

                # Set row back to pending.
                db.update_db_row_state(session, row, odl_const.PENDING)
                if exit_after_run:
                    break
                continue

            LOG.info(_LI("Syncing %(operation)s %(type)s %(uuid)s"),
                     {'operation': row.operation, 'type': row.object_type,
                      'uuid': row.object_uuid})

            # Add code to sync this to ODL
            method, urlpath, to_send = self._json_data(row)

            try:
                self.client.sendjson(method, urlpath, to_send)
                db.update_db_row_state(session, row, odl_const.COMPLETED)
            except exceptions.ConnectionError as e:
                # Don't raise the retry count, just log an error
                LOG.error(_LE("Cannot connect to the Opendaylight Controller"))
                # Set row back to pending
                db.update_db_row_state(session, row, odl_const.PENDING)
                # Break our of the loop and retry with the next
                # timer interval
                break
            except Exception as e:
                LOG.error(_LE("Error syncing %(type)s %(operation)s,"
                              " id %(uuid)s Error: %(error)s"),
                          {'type': row.object_type,
                           'uuid': row.object_uuid,
                           'operation': row.operation,
                           'error': e.message})
                db.update_pending_db_row_retry(session, row,
                                               self._row_retry_count)
