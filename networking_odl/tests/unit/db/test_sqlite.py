# Copyright 2016 Intel Corporation.
# Copyright 2016 Isaku Yamahata <isaku.yamahata at intel com>
#                               <isaku.yamahata at gmail com>
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

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.db import models
from networking_odl.tests.unit import test_base_db


class DbTestCase(test_base_db.ODLBaseDbTestCase):

    UPDATE_ROW = [odl_const.ODL_NETWORK, 'id', odl_const.ODL_UPDATE,
                  {'test': 'data'}]

    def setUp(self):
        super(DbTestCase, self).setUp()

    def _create_row(self):
        db.create_pending_row(self.db_session, *self.UPDATE_ROW)
        rows = db.get_all_db_rows(self.db_session)
        self.assertEqual(1, len(rows))
        return rows[0]

    def test_equal_created_at(self):
        row = self._create_row()
        got = self.db_session.query(models.OpendaylightJournal).filter(
            models.OpendaylightJournal.created_at == row.created_at).all()
        self.assertEqual(1, len(got))

    def test_compare_created_at(self):
        row = self._create_row()
        created_at = row.created_at + datetime.timedelta(minutes=1)
        got = self.db_session.query(models.OpendaylightJournal).filter(
            models.OpendaylightJournal.created_at < created_at).all()
        self.assertEqual(1, len(got))
