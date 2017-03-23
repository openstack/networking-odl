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

from neutron.db import api as neutron_db_api
from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_log import log as logging
from requests import exceptions

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.common import filters
from networking_odl.common import utils
from networking_odl.db import db
from networking_odl.journal import dependency_validations


LOG = logging.getLogger(__name__)


def call_thread_on_end(func):
    def new_func(obj, *args, **kwargs):
        return_value = func(obj, *args, **kwargs)
        obj.journal.set_sync_event()
        return return_value
    return new_func


def _enrich_port(plugin_context, ml2_context, object_type, operation, data):
    """Enrich the port with additional information needed by ODL"""

    # NOTE(yamahata): work around of ODL neutron northbound
    # It passes security groups in port as list of dict for historical reasons.
    # keep its format for compatibility.
    # TODO(yamahata): drop this format conversion.
    if data[odl_const.ODL_SGS]:
        groups = [{'id': id_} for id_ in data['security_groups']]
    else:
        groups = []
    new_data = copy.deepcopy(data)
    new_data[odl_const.ODL_SGS] = groups

    # NOTE(yamahata): work around for port creation for router
    # tenant_id=''(empty string) is passed when port is created
    # by l3 plugin internally for router.
    # On the other hand, ODL doesn't accept empty string for tenant_id.
    # In that case, deduce tenant_id from network_id for now.
    # Right fix: modify Neutron so that don't allow empty string
    # for tenant_id even for port for internal use.
    # TODO(yamahata): eliminate this work around when neutron side
    # is fixed
    # assert port['tenant_id'] != ''
    if ('tenant_id' not in new_data or new_data['tenant_id'] == ''):
        if ml2_context:
            network = ml2_context._network_context._network
        else:
            plugin = directory.get_plugin()
            network = plugin.get_network(plugin_context,
                                         new_data['network_id'])
        new_data['tenant_id'] = network['tenant_id']

    return new_data


def record(plugin_context, object_type, object_uuid, operation, data,
           ml2_context=None):
    if (object_type == odl_const.ODL_PORT and
            operation in (odl_const.ODL_CREATE, odl_const.ODL_UPDATE)):
        data = _enrich_port(
            plugin_context, ml2_context, object_type, operation, data)

    db.create_pending_row(plugin_context.session, object_type, object_uuid,
                          operation, data)


class OpendaylightJournalThread(object):
    """Thread worker for the Opendaylight Journal Database."""
    def __init__(self):
        self.client = client.OpenDaylightRestClient.create_client()
        self._odl_sync_timeout = cfg.CONF.ml2_odl.sync_timeout
        self._max_retry_count = cfg.CONF.ml2_odl.retry_count
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
            self._timer.cancel()
            self._start_sync_timer()
        self.event.set()

    def _start_sync_timer(self):
        self._timer = threading.Timer(self._odl_sync_timeout,
                                      self.set_sync_event)
        self._timer.start()

    def _json_data(self, row):
        data = copy.deepcopy(row.data)
        filters.filter_for_odl(row.object_type, row.operation, data)
        url_object = utils.make_url_object(row.object_type)

        if row.operation == odl_const.ODL_CREATE:
            method = 'post'
            urlpath = url_object
            to_send = {row.object_type: data}
        elif row.operation == odl_const.ODL_UPDATE:
            method = 'put'
            urlpath = url_object + '/' + row.object_uuid
            to_send = {row.object_type: data}
        elif row.operation == odl_const.ODL_DELETE:
            method = 'delete'
            urlpath = url_object + '/' + row.object_uuid
            to_send = None

        return method, urlpath, to_send

    def run_sync_thread(self):
        while True:
            try:
                self.event.wait()
                self.event.clear()

                self.sync_pending_entries()
            except Exception:
                # Catch exceptions to protect the thread while running
                LOG.exception("Error on run_sync_thread")

    def sync_pending_entries(self, exit_after_run=False):
        LOG.debug("Start processing journal entries")
        session = neutron_db_api.get_writer_session()
        entry = db.get_oldest_pending_db_row_with_lock(session)
        if entry is None:
            LOG.debug("No journal entries to process")
            return

        while entry is not None:
            log_dict = {'op': entry.operation, 'type': entry.object_type,
                        'id': entry.object_uuid}

            valid = dependency_validations.validate(session, entry)
            if not valid:
                db.update_db_row_state(session, entry, odl_const.PENDING)
                LOG.info("Skipping %(op)s %(type)s %(id)s due to "
                         "unprocessed dependencies.", log_dict)

                if exit_after_run:
                    break
                continue

            LOG.info("Processing - %(op)s %(type)s %(id)s", log_dict)
            method, urlpath, to_send = self._json_data(entry)

            try:
                self.client.sendjson(method, urlpath, to_send)
                db.update_db_row_state(session, entry, odl_const.COMPLETED)
            except exceptions.ConnectionError:
                # Don't raise the retry count, just log an error & break
                db.update_db_row_state(session, entry, odl_const.PENDING)
                LOG.error("Cannot connect to the OpenDaylight Controller,"
                          " will not process additional entries")
                break
            except Exception:
                LOG.error("Error while processing %(op)s %(type)s %(id)s",
                          log_dict, exc_info=True)
                db.update_pending_db_row_retry(
                    session, entry, self._max_retry_count)

            entry = db.get_oldest_pending_db_row_with_lock(session)
        LOG.debug("Finished processing journal entries")
