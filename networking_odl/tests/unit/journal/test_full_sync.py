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

import mock
import requests

from neutron.db import api as neutron_db_api
from neutron import manager
from neutron.tests.unit.testlib_api import SqlTestCaseLight

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.db import models
from networking_odl.journal import full_sync


class FullSyncTestCase(SqlTestCaseLight):
    def setUp(self):
        super(FullSyncTestCase, self).setUp()
        self.db_session = neutron_db_api.get_session()

        full_sync._CLIENT = mock.MagicMock()
        self.plugin_mock = mock.patch.object(manager.NeutronManager,
                                             'get_plugin').start()

        self.addCleanup(self._db_cleanup)

    def _db_cleanup(self):
        self.db_session.query(models.OpendaylightJournal).delete()

    def test_no_full_sync_when_canary_exists(self):
        full_sync.full_sync(self.db_session)
        self.assertEqual([], db.get_all_db_rows(self.db_session))

    def _mock_plugin_resources(self):
        resources = {odl_const.ODL_NETWORK: '1', odl_const.ODL_SUBNET: '2',
                     odl_const.ODL_PORT: '3'}
        plugin_instance = self.plugin_mock.return_value
        plugin_instance.get_networks.return_value = [
            {'id': resources[odl_const.ODL_NETWORK]}]
        plugin_instance.get_subnets.return_value = [
            {'id': resources[odl_const.ODL_SUBNET]}]
        plugin_instance.get_ports.return_value = [
            {'id': resources[odl_const.ODL_PORT]}]
        return resources

    def _filter_out_canary(self, rows):
        return [row for row in rows if row['object_uuid'] !=
                full_sync._CANARY_NETWORK_ID]

    def _assert_no_journal_rows(self, rows):
        self.assertEqual([], self._filter_out_canary(rows))

    def _test_no_full_sync_when_canary_in_journal(self, state):
        self._mock_canary_missing()
        self._mock_plugin_resources()
        db.create_pending_row(self.db_session, odl_const.ODL_NETWORK,
                              full_sync._CANARY_NETWORK_ID,
                              odl_const.ODL_CREATE, {})
        row = db.get_all_db_rows(self.db_session)[0]
        db.update_db_row_state(self.db_session, row, state)

        full_sync.full_sync(self.db_session)

        rows = db.get_all_db_rows(self.db_session)
        self._assert_no_journal_rows(rows)

    def test_no_full_sync_when_canary_pending_creation(self):
        self._test_no_full_sync_when_canary_in_journal(odl_const.PENDING)

    def test_no_full_sync_when_canary_is_processing(self):
        self._test_no_full_sync_when_canary_in_journal(odl_const.PROCESSING)

    def test_client_error_propagates(self):
        class TestException(Exception):
            def __init__(self):
                pass

        full_sync._CLIENT.get.side_effect = TestException()
        self.assertRaises(TestException, full_sync.full_sync, self.db_session)

    def _mock_canary_missing(self):
        get_return = mock.MagicMock()
        get_return.status_code = requests.codes.not_found
        full_sync._CLIENT.get.return_value = get_return

    def _assert_canary_created(self):
        rows = db.get_all_db_rows(self.db_session)
        self.assertTrue(any(r['object_uuid'] == full_sync._CANARY_NETWORK_ID
                            for r in rows))
        return rows

    def test_full_sync_removes_pending_rows(self):
        self._mock_canary_missing()
        db.create_pending_row(self.db_session, odl_const.ODL_NETWORK, "uuid",
                              odl_const.ODL_CREATE, {'foo': 'bar'})
        full_sync.full_sync(self.db_session)

        rows = self._assert_canary_created()
        self._assert_no_journal_rows(rows)

    def test_full_sync_no_resources(self):
        self._mock_canary_missing()
        full_sync.full_sync(self.db_session)

        rows = self._assert_canary_created()
        self._assert_no_journal_rows(rows)

    def test_full_sync_resources(self):
        self._mock_canary_missing()
        resources = self._mock_plugin_resources()

        full_sync.full_sync(self.db_session)

        rows = self._assert_canary_created()
        rows = self._filter_out_canary(rows)
        self.assertItemsEqual(resources.keys(),
                              [row['object_type'] for row in rows])
        for row in rows:
            self.assertEqual(resources[row['object_type']], row['object_uuid'])
