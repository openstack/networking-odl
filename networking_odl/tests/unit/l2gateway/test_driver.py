#
# Copyright (C) 2016 Ericsson India Global Services Pvt Ltd.
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

import copy
import mock

from networking_odl.l2gateway import driver
from neutron.tests import base


class TestOpenDaylightL2gwDriver(base.DietTestCase):

    def setUp(self):
        self.mocked_odlclient = mock.patch(
            'networking_odl.common.client'
            '.OpenDaylightRestClient.create_client').start().return_value
        self.driver = driver.OpenDaylightL2gwDriver(service_plugin=None,
                                                    validator=None)
        super(TestOpenDaylightL2gwDriver, self).setUp()

    def _get_fake_l2_gateway(self):
        fake_l2_gateway_id = "5227c228-6bba-4bbe-bdb8-6942768ff0f1"
        fake_l2_gateway = {
            "tenant_id": "de0a7495-05c4-4be0-b796-1412835c6820",
            "id": "5227c228-6bba-4bbe-bdb8-6942768ff0f1",
            "name": "test-gateway",
            "devices": [
                {
                    "device_name": "switch1",
                    "interfaces": [
                        {
                            "name": "port1",
                            "segmentation_id": [100]
                        },
                        {
                            "name": "port2",
                            "segmentation_id": [151, 152]
                        }
                    ]
                },
                {
                    "device_name": "switch2",
                    "interfaces": [
                        {
                            "name": "port5",
                            "segmentation_id": [200]
                        },
                        {
                            "name": "port6",
                            "segmentation_id": [251, 252]
                        }
                    ]
                }
            ]
        }
        return fake_l2_gateway_id, fake_l2_gateway

    def _get_fake_l2_gateway_connection(self):
        fake_l2_gateway_connection_id = "5227c228-6bba-4bbe-bdb8-6942768ff02f"
        fake_l2_gateway_connection = {
            "tenant_id": "de0a7495-05c4-4be0-b796-1412835c6820",
            "id": "5227c228-6bba-4bbe-bdb8-6942768ff02f",
            "network_id": "be0a7495-05c4-4be0-b796-1412835c6830",
            "default_segmentation_id": 77,
            "l2_gateway_id": "5227c228-6bba-4bbe-bdb8-6942768ff0f1"
        }
        return fake_l2_gateway_connection_id, fake_l2_gateway_connection

    def test_create_l2_gateway_postcommit(self):
        mocked_sendjson = self.mocked_odlclient.sendjson
        fake_l2gateway_id, fake_l2gateway = self._get_fake_l2_gateway()
        expected = {"l2_gateway": fake_l2gateway}
        self.driver.create_l2_gateway_postcommit(mock.ANY, fake_l2gateway)
        mocked_sendjson.assert_called_once_with('post', driver.L2GATEWAYS,
                                                expected)

    def test_delete_l2_gateway_postcommit(self):
        mocked_trydelete = self.mocked_odlclient.try_delete
        fake_l2gateway_id, fake_l2gateway = self._get_fake_l2_gateway()
        self.driver.delete_l2_gateway_postcommit(mock.ANY, fake_l2gateway_id)
        url = driver.L2GATEWAYS + '/' + fake_l2gateway_id
        mocked_trydelete.assert_called_once_with(url)

    def test_update_l2_gateway_postcommit(self):
        mocked_sendjson = self.mocked_odlclient.sendjson
        fake_l2gateway_id, fake_l2gateway = self._get_fake_l2_gateway()
        expected = {"l2_gateway": fake_l2gateway}
        self.driver.update_l2_gateway_postcommit(mock.ANY, fake_l2gateway)
        url = driver.L2GATEWAYS + '/' + fake_l2gateway_id
        mocked_sendjson.assert_called_once_with('put', url, expected)

    def test_create_l2_gateway_connection_postcommit(self):
        mocked_sendjson = self.mocked_odlclient.sendjson
        (fake_l2gateway_conn_id,
         fake_l2gateway_conn) = self._get_fake_l2_gateway_connection()
        expected_l2gateway_conn = copy.deepcopy(fake_l2gateway_conn)
        expected_l2gateway_conn['gateway_id'] = (
            fake_l2gateway_conn['l2_gateway_id'])
        expected_l2gateway_conn.pop('l2_gateway_id')
        expected = {"l2gateway_connection": expected_l2gateway_conn}
        self.driver.create_l2_gateway_connection_postcommit(
            mock.ANY, fake_l2gateway_conn)
        mocked_sendjson.assert_called_once_with('post',
                                                driver.L2GATEWAY_CONNECTIONS,
                                                expected)

    def test_delete_l2_gateway_connection_postcommit(self):
        mocked_trydelete = self.mocked_odlclient.try_delete
        (fake_l2gateway_conn_id,
         fake_l2gateway_conn) = self._get_fake_l2_gateway_connection()
        url = driver.L2GATEWAY_CONNECTIONS + '/' + fake_l2gateway_conn_id
        self.driver.delete_l2_gateway_connection_postcommit(
            mock.ANY, fake_l2gateway_conn_id)
        mocked_trydelete.assert_called_once_with(url)
