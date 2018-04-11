# Copyright (c) 2017 OpenStack Foundation
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

import mock

from oslo_config import fixture as config_fixture
from oslo_serialization import jsonutils
from requests import exceptions

from networking_odl.common.client import OpenDaylightRestClient
from networking_odl.common import odl_features
from networking_odl.tests import base


class TestOdlFeatures(base.DietTestCase):
    """Basic tests for odl_features"""

    feature_json = """{"features": {"feature":
                            [{"service-provider-feature":
                            "neutron-extensions:operational-port-status"}]}}"""

    def setUp(self):
        self.features_fixture = base.OpenDaylightFeaturesFixture()
        self.useFixture(self.features_fixture)
        self.cfg = self.useFixture(config_fixture.Config())
        super(TestOdlFeatures, self).setUp()
        self.features_fixture.mock_odl_features_init.stop()

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_fetch_exception(self, mocked_client):
        mocked_client.side_effect = exceptions.ConnectionError()
        self.assertIsNone(odl_features._fetch_features())

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_fetch_404(self, mocked_client):
        mocked_client.return_value = mock.MagicMock(status_code=404)
        self.assertTrue(set() == odl_features._fetch_features())

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_fetch_400(self, mocked_client):
        mocked_client.return_value = mock.MagicMock(status_code=400)
        self.assertTrue(set() == odl_features._fetch_features())

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_fetch_500(self, mocked_client):
        mocked_client.return_value = mock.MagicMock(status_code=500)
        self.assertIsNone(odl_features._fetch_features())

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_init(self, mocked_client):
        response = mock.MagicMock()
        response.status_code = 200
        response.json = mock.MagicMock(
            return_value=jsonutils.loads(self.feature_json))
        mocked_client.return_value = response

        odl_features.init()
        self.assertTrue(odl_features.has(odl_features.OPERATIONAL_PORT_STATUS))

    def test_init_from_config(self):
        self.cfg.config(odl_features='thing1,thing2', group='ml2_odl')
        odl_features.init()
        self.assertTrue(odl_features.has('thing1'))
        self.assertTrue(odl_features.has('thing2'))
