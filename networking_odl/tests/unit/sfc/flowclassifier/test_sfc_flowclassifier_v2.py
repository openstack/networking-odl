# Copyright (c) 2017 Brocade Communication Systems
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
from mock import patch

from neutron.db import api as db_api

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.sfc.flowclassifier import sfc_flowclassifier_v2 as sfc_fc
from networking_odl.tests import base as odl_base
from networking_odl.tests.unit import base_v2
from networking_odl.tests.unit.sfc import constants as sfc_const


class TestOpenDaylightSFCFlowClassifierDriverV2(
        base_v2.OpenDaylightConfigBase):

    def setUp(self):
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        super(TestOpenDaylightSFCFlowClassifierDriverV2, self).setUp()
        self.handler = sfc_fc.OpenDaylightSFCFlowClassifierDriverV2()
        self.handler.initialize()

    def _get_mock_context(self):
        mocked_fc_context = patch(
            'networking_sfc.services.flowclassifier.common.context'
            '.FlowClassifierContext').start().return_value

        mocked_fc_context.current = sfc_const.FAKE_FLOW_CLASSIFIER
        mocked_fc_context.session = self.db_context.session
        mocked_fc_context._plugin_context = mocked_fc_context
        return mocked_fc_context

    def _call_operation_object(self, operation, timing):
        method = getattr(self.handler,
                         '%s_flow_classifier_%s' % (operation, timing))
        method(self._get_mock_context())

    def _test_event(self, operation, timing):
        with db_api.context_manager.writer.using(self.db_context):
            self._call_operation_object(operation, timing)
            if timing == 'precommit':
                self.db_context.session.flush()
            row = db.get_oldest_pending_db_row_with_lock(self.db_context)

            if timing == 'precommit':
                self.assertEqual(operation, row['operation'])
                self.assertEqual(
                    odl_const.ODL_SFC_FLOW_CLASSIFIER, row['object_type'])
            elif timing == 'after':
                self.assertIsNone(row)

    # TODO(yamahata): utilize test scenarios
    def test_create_flow_classifier_precommit(self):
        self._test_event("create", "precommit")

    def test_create_flow_classifier_postcommit(self):
        self._test_event("create", "postcommit")

    def test_update_flow_classifier_precommit(self):
        self._test_event("update", "precommit")

    def test_update_flow_classifier_postcommit(self):
        self._test_event("update", "postcommit")

    def test_delete_flow_classifier_precommit(self):
        self._test_event("delete", "precommit")

    def test_delete_flow_classifier_postcommit(self):
        self._test_event("delete", "postcommit")
