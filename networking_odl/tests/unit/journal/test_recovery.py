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

from neutron.db import api as neutron_db_api
from neutron.tests.unit.testlib_api import SqlTestCaseLight

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

    def test_journal_recovery_no_rows(self):
        recovery.journal_recovery(self.db_session)
        self.assertFalse(self._CLIENT.get_resource.called)

    def _test_journal_recovery(self, operation, odl_resource, expected_state):
        db.create_pending_row(
            self.db_session, odl_const.ODL_NETWORK, 'id', operation, {})
        row = db.get_all_db_rows(self.db_session)[0]
        db.update_db_row_state(self.db_session, row, odl_const.FAILED)

        self._CLIENT.get_resource.return_value = odl_resource

        recovery.journal_recovery(self.db_session)

        row = db.get_all_db_rows(self.db_session)[0]
        self.assertEqual(expected_state, row['state'])

    def test_journal_recovery_hadles_failure_quietly(self):
        self._CLIENT.get_resource.side_effect = Exception('')
        self._test_journal_recovery(
            odl_const.ODL_DELETE, None, odl_const.FAILED)

    def test_journal_recovery_deleted_row_not_in_odl(self):
        self._test_journal_recovery(
            odl_const.ODL_DELETE, None, odl_const.COMPLETED)

    def test_journal_recovery_created_row_exists_in_odl(self):
        self._test_journal_recovery(
            odl_const.ODL_CREATE, {}, odl_const.COMPLETED)

    def test_journal_recovery_deleted_row_exists_in_odl(self):
        self._test_journal_recovery(
            odl_const.ODL_DELETE, {}, odl_const.PENDING)
