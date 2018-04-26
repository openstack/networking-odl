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
                            "neutron-extensions:operational-port-status"},
                            {"service-provider-feature":
                            "neutron-extensions:feature-with-config",
                            "configuration": "steal-your-face"}]}}"""

    feature_list = 'thing1, thing2'

    def setUp(self):
        self.features_fixture = base.OpenDaylightFeaturesFixture()
        self.useFixture(self.features_fixture)
        self.cfg = self.useFixture(config_fixture.Config())
        super(TestOdlFeatures, self).setUp()
        self.addCleanup(odl_features.deinit)

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_fetch_exception(self, mocked_client):
        mocked_client.side_effect = exceptions.ConnectionError()
        self.assertIsNone(odl_features._fetch_features())

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_fetch_404(self, mocked_client):
        mocked_client.return_value = mock.MagicMock(status_code=404)
        self.assertNotEqual(id(odl_features._fetch_features()),
                            id(odl_features.EMPTY_FEATURES))

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_fetch_400(self, mocked_client):
        mocked_client.return_value = mock.MagicMock(status_code=400)
        self.assertNotEqual(id(odl_features._fetch_features()),
                            id(odl_features.EMPTY_FEATURES))

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_fetch_500(self, mocked_client):
        mocked_client.return_value = mock.MagicMock(status_code=500)
        self.assertIsNone(odl_features._fetch_features())

    @mock.patch.object(OpenDaylightRestClient, 'request')
    def test_init(self, mocked_client):
        self.cfg.config(odl_features=None, group='ml2_odl')
        self.cfg.config(odl_features_json=None, group='ml2_odl')
        response = mock.MagicMock()
        response.status_code = 200
        response.json = mock.MagicMock(
            return_value=jsonutils.loads(self.feature_json))
        mocked_client.return_value = response

        self._assert_odl_feature_config({
            odl_features.OPERATIONAL_PORT_STATUS: '',
            'feature-with-config': 'steal-your-face',
        })

    def _assert_odl_feature_config(self, features):
        odl_features.init()
        for k, v in features.items():
            self.assertTrue(odl_features.has(k))
            self.assertEqual(odl_features.get_config(k), v)

    def test_init_from_config_json(self):
        self.cfg.config(odl_features_json=self.feature_json, group='ml2_odl')

        self._assert_odl_feature_config({
            odl_features.OPERATIONAL_PORT_STATUS: '',
            'feature-with-config': 'steal-your-face',
        })

    @mock.patch.object(odl_features, '_fetch_features')
    def test_init_without_config_calls__fetch_features(self, mock_fetch):
        self.cfg.config(odl_features_json=None, group='ml2_odl')
        self.cfg.config(odl_features=None, group='ml2_odl')
        odl_features.init()
        mock_fetch.assert_called_once()

    @mock.patch.object(odl_features, '_fetch_features')
    def test_init_from_config_list(self, mock_fetch):
        self.cfg.config(odl_features_json=None, group='ml2_odl')
        self.cfg.config(odl_features=self.feature_list, group='ml2_odl')
        odl_features.init()
        self.assertTrue(odl_features.has('thing1'))
        self.assertTrue(odl_features.has('thing2'))
        mock_fetch.assert_not_called()

    @mock.patch.object(odl_features, '_fetch_features')
    def test_init_from_json_overrides_list(self, mock_fetch):
        self.cfg.config(odl_features=self.feature_list, group='ml2_odl')
        self.cfg.config(odl_features_json=self.feature_json, group='ml2_odl')
        odl_features.init()
        self.assertFalse(odl_features.has('thing1'))
        self.assertTrue(odl_features.has('operational-port-status'))
        mock_fetch.assert_not_called()

    @mock.patch.object(odl_features, '_fetch_features')
    def test_init_with_config_does_not_call__fetch_features(self, mock_fetch):
        self.cfg.config(odl_features_json=self.feature_json, group='ml2_odl')
        odl_features.init()
        mock_fetch.assert_not_called()

    def test_init_from_config_malformed_json_raises_exception(self):
        malformed_json = ")]}'" + self.feature_json
        self.cfg.config(odl_features_json=malformed_json, group='ml2_odl')
        self.assertRaises(ValueError, odl_features.init)

    def test_init_from_config_json_not_in_odl_format_raises_exception(self):
        self.cfg.config(odl_features_json='{}', group='ml2_odl')
        self.assertRaises(KeyError, odl_features.init)


class TestOdlFeaturesNoFixture(base.DietTestCase):
    """Basic tests for odl_features that don't call init()"""

    def setUp(self):
        super(TestOdlFeaturesNoFixture, self).setUp()
        self.addCleanup(odl_features.deinit)

    def test_feature_configs_does_not_mutate_default_features(self):
        self.assertEqual(odl_features.EMPTY_FEATURES,
                         odl_features.feature_configs)
        odl_features.feature_configs['test'] = True
        self.assertNotEqual(odl_features.EMPTY_FEATURES,
                            odl_features.feature_configs)

    def test_deinit_does_not_mutate_default_features(self):
        # we call it before initing anything, to force the reassignment
        # of the global features variable.
        odl_features.deinit()
        odl_features.feature_configs['test'] = True
        self.assertNotEqual(odl_features.EMPTY_FEATURES,
                            odl_features.feature_configs)
        # now we do it again, to make sure that it assigns it to default
        # values
        odl_features.deinit()
        self.assertEqual(odl_features.EMPTY_FEATURES,
                         odl_features.feature_configs)

    def test_deinit_resets_to_default_features(self):
        odl_features.deinit()
        self.assertEqual(odl_features.feature_configs,
                         odl_features.EMPTY_FEATURES)
