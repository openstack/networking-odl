# Copyright (c) 2016 Brocade Communication Systems
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
from neutron.tests import base

from networking_odl.common.client import OpenDaylightRestClient as client
from networking_odl.sfc.flowclassifier import sfc_flowclassifier_v1 as sfc_fc
from networking_odl.tests import base as odl_base
from networking_odl.tests.unit.sfc import constants as sfc_const


class TestOpenDaylightSFCFlowClassifierDriverV1(base.DietTestCase):

    def setUp(self):
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        self.mocked_fc_context = patch(
            'networking_sfc.services.flowclassifier.common.context'
            '.FlowClassifierContext').start().return_value
        super(TestOpenDaylightSFCFlowClassifierDriverV1, self).setUp()

        self.driver = sfc_fc.OpenDaylightSFCFlowClassifierDriverV1()
        self.driver.initialize()
        self.mocked_fc_context.current = sfc_const.FAKE_FLOW_CLASSIFIER

    @patch.object(client, 'sendjson')
    def test_create_flow_classifier(self, mocked_sendjson):
        expected = {"flowclassifier": sfc_const.FAKE_FLOW_CLASSIFIER}
        self.driver.create_flow_classifier(self.mocked_fc_context)
        mocked_sendjson.assert_called_once_with(
            'post', sfc_const.CLASSIFIERS_BASE_URI, expected)

    @patch.object(client, 'sendjson')
    def test_update_flow_classifier(self, mocked_sendjson):
        expected = {"flowclassifier": sfc_const.FAKE_FLOW_CLASSIFIER}
        self.driver.update_flow_classifier(self.mocked_fc_context)
        mocked_sendjson.assert_called_once_with(
            'put', sfc_const.CLASSIFIERS_BASE_URI +
            '/' + sfc_const.FAKE_FLOW_CLASSIFIER_ID, expected)

    @patch.object(client, 'try_delete')
    def test_delete_flow_classifier(self, mocked_try_delete):
        self.driver.delete_flow_classifier(self.mocked_fc_context)
        mocked_try_delete.assert_called_once_with(
            sfc_const.CLASSIFIERS_BASE_URI + '/' +
            sfc_const.FAKE_FLOW_CLASSIFIER_ID)
