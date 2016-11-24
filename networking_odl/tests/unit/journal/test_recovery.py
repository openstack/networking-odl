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

from neutron.db import api as neutron_db_api
from neutron.tests.unit.testlib_api import SqlTestCaseLight
from neutron_lib import exceptions as nexc
from neutron_lib.plugins import directory

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.db import models
from networking_odl.journal import recovery
from networking_odl.tests import base


class RecoveryTestCase(SqlTestCaseLight):
    def setUp(self):
        super(RecoveryTestCase, self).setUp()
        self.db_session = neutron_db_api.get_session()

        self.useFixture(
            base.OpenDaylightRestClientGlobalFixture(recovery._CLIENT))
        self._CLIENT = recovery._CLIENT.get_client()

        self.addCleanup(self._db_cleanup)

    def _db_cleanup(self):
        self.db_session.query(models.OpendaylightJournal).delete()

    def _mock_resource(self, plugin, resource_type):
        mock_resource = mock.MagicMock()
        get_func = getattr(plugin, 'get_{}'.format(resource_type))
        get_func.return_value = mock_resource
        return mock_resource

    def _mock_row(self, resource_type):
        return mock.MagicMock(object_type=resource_type)

    def _test__get_latest_resource(self, plugin, resource_type):
        mock_resource = self._mock_resource(plugin, resource_type)
        mock_row = self._mock_row(resource_type)

        resource = recovery._get_latest_resource(mock_row)
        self.assertEqual(mock_resource, resource)

    @mock.patch.object(directory, 'get_plugin')
    def test__get_latest_resource_l2(self, plugin_mock):
        for resource_type in odl_const.L2_RESOURCES:
            plugin = plugin_mock.return_value
            self._test__get_latest_resource(plugin, resource_type)

    @mock.patch.object(directory, 'get_plugin')
    def test__get_latest_resource_l3(self, plugin_mock):
        for resource_type in odl_const.L3_RESOURCES:
            plugin = plugin_mock.return_value
            self._test__get_latest_resource(plugin, resource_type)

    def test__get_latest_resource_unsupported(self):
        mock_row = self._mock_row('aaa')
        self.assertRaises(
            recovery.UnsupportedResourceType, recovery._get_latest_resource,
            mock_row)

    @mock.patch.object(directory, 'get_plugin')
    def test__get_latest_resource_none(self, plugin_mock):
        plugin_mock.return_value.get_network.side_effect = nexc.NotFound()

        mock_row = self._mock_row(odl_const.ODL_NETWORK)
        self.assertRaises(
            nexc.NotFound, recovery._get_latest_resource, mock_row)

    def test_journal_recovery_no_rows(self):
        recovery.journal_recovery(self.db_session)
        self.assertFalse(self._CLIENT.get_resource.called)

    def _test_recovery(self, operation, odl_resource, expected_state):
        db.create_pending_row(
            self.db_session, odl_const.ODL_NETWORK, 'id', operation, {})
        created_row = db.get_all_db_rows(self.db_session)[0]
        db.update_db_row_state(self.db_session, created_row, odl_const.FAILED)

        self._CLIENT.get_resource.return_value = odl_resource

        recovery.journal_recovery(self.db_session)

        row = db.get_all_db_rows_by_state(self.db_session, expected_state)[0]
        self.assertEqual(created_row['seqnum'], row['seqnum'])
        return created_row

    def test_journal_recovery_hadles_failure_quietly(self):
        self._CLIENT.get_resource.side_effect = Exception('')
        self._test_recovery(
            odl_const.ODL_DELETE, None, odl_const.FAILED)

    def test_journal_recovery_deleted_row_not_in_odl(self):
        self._test_recovery(odl_const.ODL_DELETE, None, odl_const.COMPLETED)

    def test_journal_recovery_created_row_exists_in_odl(self):
        self._test_recovery(odl_const.ODL_CREATE, {}, odl_const.COMPLETED)

    def test_journal_recovery_deleted_row_exists_in_odl(self):
        self._test_recovery(odl_const.ODL_DELETE, {}, odl_const.PENDING)

    @mock.patch.object(recovery, '_get_latest_resource')
    def _test_recovery_creates_operation(
            self, operation, resource, odl_resource, expected_operation,
            recovery_mock):
        if resource is not None:
            recovery_mock.return_value = resource
        else:
            recovery_mock.side_effect = nexc.NotFound
        original_row = self._test_recovery(
            operation, odl_resource, odl_const.COMPLETED)

        pending_row = db.get_all_db_rows_by_state(
            self.db_session, odl_const.PENDING)[0]
        self.assertEqual(expected_operation, pending_row['operation'])
        self.assertEqual(original_row['object_type'],
                         pending_row['object_type'])
        self.assertEqual(original_row['object_uuid'],
                         pending_row['object_uuid'])

    def test_recovery_created_row_not_in_odl(self):
        self._test_recovery_creates_operation(
            odl_const.ODL_CREATE, {}, None, odl_const.ODL_CREATE)

    def test_recovery_updated_row_not_in_odl(self):
        self._test_recovery_creates_operation(
            odl_const.ODL_UPDATE, {}, None, odl_const.ODL_CREATE)

    def test_recovery_updated_resource_missing_but_exists_in_odl(self):
        self._test_recovery_creates_operation(
            odl_const.ODL_UPDATE, None, {}, odl_const.ODL_DELETE)

    @mock.patch.object(recovery, '_get_latest_resource')
    def test_recovery_created_resource_missing_and_not_in_odl(self, rmock):
        rmock.return_value = None
        self._test_recovery(odl_const.ODL_CREATE, None, odl_const.COMPLETED)

    @mock.patch.object(recovery, '_get_latest_resource')
    def test_recovery_updated_resource_missing_and_not_in_odl(self, rmock):
        rmock.return_value = None
        self._test_recovery(odl_const.ODL_UPDATE, None, odl_const.COMPLETED)
