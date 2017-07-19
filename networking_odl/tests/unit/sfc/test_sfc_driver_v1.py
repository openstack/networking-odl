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

from networking_odl.common.client import OpenDaylightRestClient as client
from networking_odl.sfc import sfc_driver_v1
from networking_odl.tests import base as odl_base
from networking_odl.tests.unit.sfc import constants as sfc_const

from neutron.tests import base


class TestOpenDaylightSFCDriverV1(base.DietTestCase):

    def setUp(self):
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        self.mocked_pp_context = patch(
            'networking_sfc.services.sfc.common.context.PortPairContext'
        ).start().return_value

        self.mocked_ppg_context = patch(
            'networking_sfc.services.sfc.common.context.PortPairGroupContext'
        ).start().return_value

        self.mocked_pc_context = patch(
            'networking_sfc.services.sfc.common.context.PortChainContext'
        ).start().return_value
        super(TestOpenDaylightSFCDriverV1, self).setUp()

        self.driver = sfc_driver_v1.OpenDaylightSFCDriverV1()
        self.driver.initialize()
        self.mocked_pp_context.current = sfc_const.FAKE_PORT_PAIR
        self.mocked_ppg_context.current = sfc_const.FAKE_PORT_PAIR_GROUP
        self.mocked_pc_context.current = sfc_const.FAKE_PORT_CHAIN

    @patch.object(client, 'sendjson')
    def test_create_port_pair(self, mocked_sendjson):
        expected = {"portpair": sfc_const.FAKE_PORT_PAIR}
        self.driver.create_port_pair(self.mocked_pp_context)
        mocked_sendjson.assert_called_once_with(
            'post', sfc_const.PORT_PAIRS_BASE_URI, expected)

    @patch.object(client, 'sendjson')
    def test_update_port_pair(self, mocked_sendjson):
        expected = {"portpair": sfc_const.FAKE_PORT_PAIR}
        self.driver.update_port_pair(self.mocked_pp_context)
        mocked_sendjson.assert_called_once_with(
            'put', sfc_const.PORT_PAIRS_BASE_URI + '/' +
            sfc_const.FAKE_PORT_PAIR_ID, expected)

    @patch.object(client, 'try_delete')
    def test_delete_port_pair(self, mocked_try_delete):
        self.driver.delete_port_pair(self.mocked_pp_context)
        mocked_try_delete.assert_called_once_with(
            sfc_const.PORT_PAIRS_BASE_URI + '/' + sfc_const.FAKE_PORT_PAIR_ID)

    @patch.object(client, 'sendjson')
    def test_create_port_pair_group(self, mocked_sendjson):
        expected = {"portpairgroup": sfc_const.FAKE_PORT_PAIR_GROUP}
        self.driver.create_port_pair_group(self.mocked_ppg_context)
        mocked_sendjson.assert_called_once_with(
            'post', sfc_const.PORT_PAIR_GROUPS_BASE_URI, expected)

    @patch.object(client, 'sendjson')
    def test_update_port_pair_group(self, mocked_sendjson):
        expected = {"portpairgroup": sfc_const.FAKE_PORT_PAIR_GROUP}
        self.driver.update_port_pair_group(self.mocked_ppg_context)
        mocked_sendjson.assert_called_once_with(
            'put', sfc_const.PORT_PAIR_GROUPS_BASE_URI + '/' +
            sfc_const.FAKE_PORT_PAIR_GROUP_ID, expected)

    @patch.object(client, 'try_delete')
    def test_delete_port_pair_group(self, mocked_try_delete):
        self.driver.delete_port_pair_group(self.mocked_ppg_context)
        mocked_try_delete.assert_called_once_with(
            sfc_const.PORT_PAIR_GROUPS_BASE_URI + '/' +
            sfc_const.FAKE_PORT_PAIR_GROUP_ID)

    @patch.object(client, 'sendjson')
    def test_create_port_chain(self, mocked_sendjson):
        expected = {"portchain": sfc_const.FAKE_PORT_CHAIN}
        self.driver.create_port_chain(self.mocked_pc_context)
        mocked_sendjson.assert_called_once_with(
            'post', sfc_const.PORT_CHAINS_BASE_URI, expected)

    @patch.object(client, 'sendjson')
    def test_update_port_chain(self, mocked_sendjson):
        expected = {"portchain": sfc_const.FAKE_PORT_CHAIN}
        self.driver.update_port_chain(self.mocked_pc_context)
        mocked_sendjson.assert_called_once_with(
            'put', sfc_const.PORT_CHAINS_BASE_URI + '/' +
            sfc_const.FAKE_PORT_CHAIN_ID, expected)

    @patch.object(client, 'try_delete')
    def test_delete_port_chain(self, mocked_try_delete):
        self.driver.delete_port_chain(self.mocked_pc_context)
        mocked_try_delete.assert_called_once_with(
            sfc_const.PORT_CHAINS_BASE_URI + '/' +
            sfc_const.FAKE_PORT_CHAIN_ID)
