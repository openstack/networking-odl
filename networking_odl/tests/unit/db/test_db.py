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

from datetime import datetime
from datetime import timedelta

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.db import models

from neutron.db import api as neutron_db_api
from neutron.tests.unit.testlib_api import SqlTestCaseLight
from unittest2.case import TestCase


class DbTestCase(SqlTestCaseLight, TestCase):

    UPDATE_ROW = [odl_const.ODL_NETWORK, 'id', odl_const.ODL_UPDATE,
                  {'test': 'data'}]

    def setUp(self):
        super(DbTestCase, self).setUp()
        self.db_session = neutron_db_api.get_session()
        self.addCleanup(self._db_cleanup)

    def _db_cleanup(self):
        self.db_session.query(models.OpendaylightJournal).delete()

    def _update_row(self, row):
        self.db_session.merge(row)
        self.db_session.flush()

    def _test_validate_updates(self, rows, time_deltas, expected_validations):
        for row in rows:
            db.create_pending_row(self.db_session, *row)

        # update row created_at
        rows = db.get_all_db_rows(self.db_session)
        now = datetime.now()
        for row, time_delta in zip(rows, time_deltas):
            row.created_at = now - timedelta(hours=time_delta)
            self._update_row(row)

        # validate if there are older rows
        for row, expected_valid in zip(rows, expected_validations):
            valid = not db.check_for_older_ops(self.db_session, row)
            self.assertEqual(expected_valid, valid)

    def test_validate_updates_same_object_uuid(self):
        self._test_validate_updates(
            [self.UPDATE_ROW, self.UPDATE_ROW], [1, 0], [True, False])

    def test_validate_updates_same_created_time(self):
        self._test_validate_updates(
            [self.UPDATE_ROW, self.UPDATE_ROW], [0, 0], [True, True])

    def test_validate_updates_different_object_uuid(self):
        other_row = list(self.UPDATE_ROW)
        other_row[1] += 'a'
        self._test_validate_updates(
            [self.UPDATE_ROW, other_row], [1, 0], [True, True])

    def test_validate_updates_different_object_type(self):
        other_row = list(self.UPDATE_ROW)
        other_row[0] = odl_const.ODL_PORT
        other_row[1] += 'a'
        self._test_validate_updates(
            [self.UPDATE_ROW, other_row], [1, 0], [True, True])
