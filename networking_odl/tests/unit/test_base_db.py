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

from neutron.tests.unit.testlib_api import SqlTestCaseLight
from neutron_lib import context

from networking_odl.common import constants
from networking_odl.db import models


class ODLBaseDbTestCase(SqlTestCaseLight):
    def setUp(self):
        super(ODLBaseDbTestCase, self).setUp()
        self.db_context = context.get_admin_context()
        self.db_session = self.db_context.session
        self.addCleanup(self._db_cleanup)

    def _db_cleanup(self):
        self.db_session.query(models.OpenDaylightJournal).delete()
        self.db_session.query(models.OpenDaylightPeriodicTask).delete()
        row0 = models.OpenDaylightPeriodicTask(
            task='maintenance', state=constants.PENDING)
        row1 = models.OpenDaylightPeriodicTask(
            task='hostconfig', state=constants.PENDING)
        self.db_session.merge(row0)
        self.db_session.merge(row1)
        self.db_session.flush()
