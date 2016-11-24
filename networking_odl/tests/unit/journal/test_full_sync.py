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

from neutron_lib import constants
from neutron_lib.plugins import directory

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.journal import full_sync
from networking_odl.tests import base
from networking_odl.tests.unit import test_base_db


class FullSyncTestCase(test_base_db.ODLBaseDbTestCase):
    def setUp(self):
        super(FullSyncTestCase, self).setUp()

        self.useFixture(
            base.OpenDaylightRestClientGlobalFixture(full_sync._CLIENT))
        self._CLIENT = full_sync._CLIENT.get_client()
        self.plugin = mock.MagicMock()
        self.l3_plugin = mock.MagicMock()
        directory.add_plugin(constants.CORE, self.plugin)
        directory.add_plugin(constants.L3, self.l3_plugin)

    def test_no_full_sync_when_canary_exists(self):
        full_sync.full_sync(self.db_session)
        self.assertEqual([], db.get_all_db_rows(self.db_session))

    def _mock_l2_resources(self):
        expected_journal = {odl_const.ODL_NETWORK: '1',
                            odl_const.ODL_SUBNET: '2',
                            odl_const.ODL_PORT: '3'}
        self.plugin.get_networks.return_value = [
            {'id': expected_journal[odl_const.ODL_NETWORK]}]
        self.plugin.get_subnets.return_value = [
            {'id': expected_journal[odl_const.ODL_SUBNET]}]
        self.plugin.get_ports.side_effect = ([
            {'id': expected_journal[odl_const.ODL_PORT]}], [])
        return expected_journal

    def _filter_out_canary(self, rows):
        return [row for row in rows if row['object_uuid'] !=
                full_sync._CANARY_NETWORK_ID]

    def _test_no_full_sync_when_canary_in_journal(self, state):
        self._mock_canary_missing()
        self._mock_l2_resources()
        db.create_pending_row(self.db_session, odl_const.ODL_NETWORK,
                              full_sync._CANARY_NETWORK_ID,
                              odl_const.ODL_CREATE, {})
        row = db.get_all_db_rows(self.db_session)[0]
        db.update_db_row_state(self.db_session, row, state)

        full_sync.full_sync(self.db_session)

        rows = db.get_all_db_rows(self.db_session)
        self.assertEqual([], self._filter_out_canary(rows))

    def test_no_full_sync_when_canary_pending_creation(self):
        self._test_no_full_sync_when_canary_in_journal(odl_const.PENDING)

    def test_no_full_sync_when_canary_is_processing(self):
        self._test_no_full_sync_when_canary_in_journal(odl_const.PROCESSING)

    def test_client_error_propagates(self):
        class TestException(Exception):
            def __init__(self):
                pass

        self._CLIENT.get.side_effect = TestException()
        self.assertRaises(TestException, full_sync.full_sync, self.db_session)

    def _mock_canary_missing(self):
        get_return = mock.MagicMock()
        get_return.status_code = requests.codes.not_found
        self._CLIENT.get.return_value = get_return

    def _assert_canary_created(self):
        rows = db.get_all_db_rows(self.db_session)
        self.assertTrue(any(r['object_uuid'] == full_sync._CANARY_NETWORK_ID
                            for r in rows))
        return rows

    def _test_full_sync_resources(self, expected_journal):
        self._mock_canary_missing()

        full_sync.full_sync(self.db_session)

        rows = self._assert_canary_created()
        rows = self._filter_out_canary(rows)
        self.assertItemsEqual(expected_journal.keys(),
                              [row['object_type'] for row in rows])
        for row in rows:
            self.assertEqual(expected_journal[row['object_type']],
                             row['object_uuid'])

    def test_full_sync_removes_pending_rows(self):
        db.create_pending_row(self.db_session, odl_const.ODL_NETWORK, "uuid",
                              odl_const.ODL_CREATE, {'foo': 'bar'})
        self._test_full_sync_resources({})

    def test_full_sync_no_resources(self):
        self._test_full_sync_resources({})

    def test_full_sync_l2_resources(self):
        self._test_full_sync_resources(self._mock_l2_resources())

    def _mock_router_port(self, port_id):
        router_port = {'id': port_id,
                       'device_id': '1',
                       'tenant_id': '1',
                       'fixed_ips': [{'subnet_id': '1'}]}
        self.plugin.get_ports.side_effect = ([], [router_port])

    def _mock_l3_resources(self):
        expected_journal = {odl_const.ODL_ROUTER: '1',
                            odl_const.ODL_FLOATINGIP: '2'}
        self.l3_plugin.get_routers.return_value = [
            {'id': expected_journal[odl_const.ODL_ROUTER]}]
        self.l3_plugin.get_floatingips.return_value = [
            {'id': expected_journal[odl_const.ODL_FLOATINGIP]}]

        return expected_journal

    def test_full_sync_l3_resources(self):
        self._test_full_sync_resources(self._mock_l3_resources())
