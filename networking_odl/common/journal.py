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
from networking_odl.db import db
from networking_odl.openstack.common._i18n import _LE
from networking_odl.openstack.common._i18n import _LI

LOG = logging.getLogger(__name__)


def call_thread_on_end(func):
    def new_func(obj, *args):
        func(obj, *args)
        obj.journal.start_odl_sync_thread()
    return new_func


class OpendaylightJournalThread(object):
    """Thread worker for the Opendaylight Journal Database."""
    def __init__(self):
        self.client = client.OpenDaylightRestClient.create_client()
        self._odl_sync_timeout = cfg.CONF.ml2_odl.sync_timeout
        self._row_retry_count = cfg.CONF.ml2_odl.retry_count
        self.event = threading.Event()
        self.start_odl_sync_thread()

    def start_odl_sync_thread(self):
        # Reset timer
        if hasattr(self, 'timer'):
            LOG.debug("Resetting thread timer")
            self.timer.cancel()
            self.timer = None
        self.timer = threading.Timer(self._odl_sync_timeout,
                                     self.start_odl_sync_thread)
        self.timer.start()

        # Don't start a second thread if there is one alive already
        # Only trigger the event
        if (hasattr(self, '_odl_sync_thread') and
           self._odl_sync_thread.isAlive()):
            LOG.debug("Thread alive, sending event")
            self.event.set()
            return

        # Start the sync thread if there isn't one
        LOG.debug("Starting a new sync thread")
        self._odl_sync_thread = threading.Thread(
            name='sync',
            target=self.sync_pending_row)

        self._odl_sync_thread.start()

    def _json_data(self, row):
        filter_cls = filters.FILTER_MAP[row.object_type]

        if row.operation == odl_const.ODL_CREATE:
            method = 'post'
            attr_filter = filter_cls.filter_create_attributes
            data = copy.deepcopy(row.data)
            urlpath = row.object_type + 's'
            attr_filter(data)
            to_send = {row.object_type: data}
        elif row.operation == odl_const.ODL_UPDATE:
            method = 'put'
            attr_filter = filter_cls.filter_update_attributes
            data = copy.deepcopy(row.data)
            urlpath = row.object_type + 's/' + row.object_uuid
            attr_filter(data)
            to_send = {row.object_type: data}
        elif row.operation == odl_const.ODL_DELETE:
            method = 'delete'
            data = None
            urlpath = row.object_type + 's/' + row.object_uuid
            to_send = None

        return method, urlpath, to_send

    def sync_pending_row(self, exit_after_run=False):
        # Block until all pending rows are processed
        session = neutron_db_api.get_session()
        while not self.event.is_set():
            self.event.wait()
            # Clear the event and go back to waiting after
            # the sync block exits
            self.event.clear()
            while True:
                LOG.debug("Thread walking database")
                row = db.get_oldest_pending_db_row_with_lock(session)
                if not row:
                    LOG.debug("No rows to sync")
                    break

                # Validate the operation
                validate_func = db.VALIDATION_MAP[row.object_type]
                valid = validate_func(session, row.object_uuid,
                                      row.operation, row.data)
                if not valid:
                    LOG.info(_LI("%(operation)s %(type)s %(uuid)s is not a "
                                 "valid operation yet, skipping for now"),
                             {'operation': row.operation,
                              'type': row.object_type,
                              'uuid': row.object_uuid})
                    continue

                LOG.info(_LI("Syncing %(operation)s %(type)s %(uuid)s"),
                         {'operation': row.operation, 'type': row.object_type,
                          'uuid': row.object_uuid})

                # Add code to sync this to ODL
                method, urlpath, to_send = self._json_data(row)

                try:
                    self.client.sendjson(method, urlpath, to_send)
                    db.update_processing_db_row_passed(session, row)
                except exceptions.ConnectionError as e:
                    # Don't raise the retry count, just log an error
                    LOG.error(_LE("Cannot connect to the Opendaylight "
                                  "Controller"))
                    # Set row back to pending
                    db.update_db_row_pending(session, row)
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
            LOG.debug("Clearing sync thread event")
            if exit_after_run:
                # Permanently waiting thread model breaks unit tests
                # Adding this arg to exit here only for unit tests
                break
