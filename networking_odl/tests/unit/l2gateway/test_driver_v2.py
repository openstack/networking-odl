#
# Copyright (C) 2017 Ericsson India Global Services Pvt Ltd.
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

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.l2gateway import driver_v2 as driverv2
from networking_odl.tests.unit import base_v2


class OpenDaylightL2GWDriverTestCase(base_v2.OpenDaylightConfigBase):

    def setUp(self):
        super(OpenDaylightL2GWDriverTestCase, self).setUp()
        self.driver = driverv2.OpenDaylightL2gwDriver(service_plugin=None)

    def _get_fake_l2_gateway(self):
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
        return fake_l2_gateway

    def _get_fake_l2_gateway_connection(self):
        fake_l2_gateway_connection = {
            "tenant_id": "de0a7495-05c4-4be0-b796-1412835c6820",
            "id": "5227c228-6bba-4bbe-bdb8-6942768ff02f",
            "network_id": "be0a7495-05c4-4be0-b796-1412835c6830",
            "default_segmentation_id": 77,
            "l2_gateway_id": "5227c228-6bba-4bbe-bdb8-6942768ff0f1"
        }
        return fake_l2_gateway_connection

    def _assert_op(self, operation, object_type, data, precommit=True):
        row = db.get_oldest_pending_db_row_with_lock(self.db_session)
        if precommit:
            self.db_session.flush()
            self.assertEqual(operation, row['operation'])
            self.assertEqual(object_type, row['object_type'])
            self.assertEqual(data['id'], row['object_uuid'])
        else:
            self.assertIsNone(row)

    def test_create_l2_gateway(self):
        fake_data = self._get_fake_l2_gateway()
        self.driver.create_l2_gateway_precommit(self.db_context, fake_data)
        self._assert_op(odl_const.ODL_CREATE, odl_const.ODL_L2GATEWAY,
                        fake_data)
        self.driver.create_l2_gateway_postcommit(self.db_context, fake_data)
        self._assert_op(odl_const.ODL_CREATE, odl_const.ODL_L2GATEWAY,
                        fake_data, False)

    def test_delete_l2_gateway(self):
        fake_data = self._get_fake_l2_gateway()
        self.driver.delete_l2_gateway_precommit(self.db_context,
                                                fake_data['id'])
        self._assert_op(odl_const.ODL_DELETE, odl_const.ODL_L2GATEWAY,
                        fake_data)
        self.driver.delete_l2_gateway_postcommit(self.db_context,
                                                 fake_data['id'])
        self._assert_op(odl_const.ODL_DELETE, odl_const.ODL_L2GATEWAY,
                        fake_data, False)

    def test_update_l2_gateway(self):
        fake_data = self._get_fake_l2_gateway()
        self.driver.update_l2_gateway_precommit(self.db_context, fake_data)
        self._assert_op(odl_const.ODL_UPDATE, odl_const.ODL_L2GATEWAY,
                        fake_data)
        self.driver.update_l2_gateway_postcommit(self.db_context, fake_data)
        self._assert_op(odl_const.ODL_UPDATE, odl_const.ODL_L2GATEWAY,
                        fake_data, False)

    def test_create_l2_gateway_connection(self):
        fake_data = self._get_fake_l2_gateway_connection()
        self.driver.create_l2_gateway_connection_precommit(self.db_context,
                                                           fake_data)
        self._assert_op(odl_const.ODL_CREATE,
                        odl_const.ODL_L2GATEWAY_CONNECTION,
                        fake_data)
        self.driver.create_l2_gateway_connection_postcommit(self.db_context,
                                                            fake_data)
        self._assert_op(odl_const.ODL_CREATE,
                        odl_const.ODL_L2GATEWAY_CONNECTION,
                        fake_data, False)

    def test_delete_l2_gateway_connection(self):
        fake_data = self._get_fake_l2_gateway_connection()
        self.driver.delete_l2_gateway_connection_precommit(self.db_context,
                                                           fake_data['id'])
        self._assert_op(odl_const.ODL_DELETE,
                        odl_const.ODL_L2GATEWAY_CONNECTION,
                        fake_data)
        self.driver.delete_l2_gateway_connection_postcommit(self.db_context,
                                                            fake_data['id'])
        self._assert_op(odl_const.ODL_DELETE,
                        odl_const.ODL_L2GATEWAY_CONNECTION,
                        fake_data, False)
