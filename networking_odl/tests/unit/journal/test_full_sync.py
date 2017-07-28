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

import mock
import requests

from networking_l2gw.services.l2gateway.common import constants as l2gw_const
from networking_sfc.extensions import flowclassifier as fc_const
from networking_sfc.extensions import sfc as sfc_const
from neutron.services.trunk import constants as t_consts
from neutron_lib.api.definitions import bgpvpn as bgpvpn_const
from neutron_lib.plugins import constants
from neutron_lib.plugins import directory

from networking_odl.bgpvpn import odl_v2 as bgpvpn_driver
from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.journal import full_sync
from networking_odl.journal import journal
from networking_odl.l2gateway import driver_v2 as l2gw_driver
from networking_odl.l3 import l3_odl_v2
from networking_odl.lbaas import lbaasv2_driver_v2 as lbaas_driver
from networking_odl.ml2 import mech_driver_v2
from networking_odl.qos import qos_driver_v2 as qos_driver
from networking_odl.sfc.flowclassifier import sfc_flowclassifier_v2
from networking_odl.sfc import sfc_driver_v2 as sfc_driver
from networking_odl.tests import base
from networking_odl.tests.unit import test_base_db
from networking_odl.trunk import trunk_driver_v2 as trunk_driver


class FullSyncTestCase(test_base_db.ODLBaseDbTestCase):
    def setUp(self):
        self.useFixture(
            base.OpenDaylightRestClientGlobalFixture(full_sync._CLIENT))
        super(FullSyncTestCase, self).setUp()

        self._CLIENT = full_sync._CLIENT.get_client()

        for plugin_name in self._get_all_resources():
            mocked = mock.MagicMock()
            if plugin_name == constants.CORE:
                self.plugin = mocked
            elif plugin_name == constants.L3:
                self.l3_plugin = mocked

            directory.add_plugin(plugin_name, mocked)

        self.addCleanup(self.clean_registered_resources)

    @staticmethod
    def _get_all_resources():
        return {
            constants.L3: l3_odl_v2.L3_RESOURCES,
            constants.CORE: mech_driver_v2.L2_RESOURCES,
            constants.LOADBALANCERV2: lbaas_driver.LBAAS_RESOURCES,
            t_consts.TRUNK: trunk_driver.TRUNK_RESOURCES,
            constants.QOS: qos_driver.QOS_RESOURCES,
            sfc_const.SFC_EXT: sfc_driver.SFC_RESOURCES,
            bgpvpn_const.LABEL: bgpvpn_driver.BGPVPN_RESOURCES,
            fc_const.FLOW_CLASSIFIER_EXT:
                sfc_flowclassifier_v2.SFC_FC_RESOURCES,
            l2gw_const.L2GW: l2gw_driver.L2GW_RESOURCES,
        }

    @staticmethod
    def clean_registered_resources():
        full_sync.ALL_RESOURCES = {}

    def test_no_full_sync_when_canary_exists(self):
        full_sync.full_sync(self.db_context)
        self.assertEqual([], db.get_all_db_rows(self.db_session))

    def _mock_l2_resources(self):
        expected_journal = {odl_const.ODL_NETWORK: '1',
                            odl_const.ODL_SUBNET: '2',
                            odl_const.ODL_PORT: '3'}
        network_id = expected_journal[odl_const.ODL_NETWORK]
        self.plugin.get_networks.return_value = [{'id': network_id}]
        self.plugin.get_subnets.return_value = [
            {'id': expected_journal[odl_const.ODL_SUBNET],
             'network_id': network_id}]
        port = {'id': expected_journal[odl_const.ODL_PORT],
                odl_const.ODL_SGS: None,
                'tenant_id': '123',
                'fixed_ips': [],
                'network_id': network_id}
        self.plugin.get_ports.side_effect = ([port], [])
        return expected_journal

    def _filter_out_canary(self, rows):
        return [row for row in rows if row['object_uuid'] !=
                full_sync._CANARY_NETWORK_ID]

    def _test_no_full_sync_when_canary_in_journal(self, state):
        self._mock_canary_missing()
        self._mock_l2_resources()
        db.create_pending_row(self.db_session, odl_const.ODL_NETWORK,
                              full_sync._CANARY_NETWORK_ID,
                              odl_const.ODL_CREATE, {})
        row = db.get_all_db_rows(self.db_session)[0]
        db.update_db_row_state(self.db_session, row, state)

        full_sync.full_sync(self.db_context)

        rows = db.get_all_db_rows(self.db_session)
        self.assertEqual([], self._filter_out_canary(rows))

    def test_no_full_sync_when_canary_pending_creation(self):
        self._test_no_full_sync_when_canary_in_journal(odl_const.PENDING)

    def test_no_full_sync_when_canary_is_processing(self):
        self._test_no_full_sync_when_canary_in_journal(odl_const.PROCESSING)

    @mock.patch.object(db, 'delete_pending_rows')
    @mock.patch.object(full_sync, '_full_sync_needed')
    @mock.patch.object(full_sync, '_sync_resources')
    @mock.patch.object(journal, 'record')
    def test_sync_resource_order(
            self, record_mock, _sync_resources_mock, _full_sync_needed_mock,
            delete_pending_rows_mock):

        full_sync.ALL_RESOURCES = self._get_all_resources()
        _full_sync_needed_mock._full_sync_needed.return_value = True
        context = mock.MagicMock()
        full_sync.full_sync(context)

        _sync_resources_mock.assert_has_calls(
            [mock.call(mock.ANY, mock.ANY, object_type, collection_name)
                for (object_type, collection_name) in [
                    (odl_const.ODL_SG, odl_const.ODL_SGS),
                    (odl_const.ODL_SG_RULE, odl_const.ODL_SG_RULES),
                    (odl_const.ODL_NETWORK, odl_const.ODL_NETWORKS),
                    (odl_const.ODL_SUBNET, odl_const.ODL_SUBNETS),
                    (odl_const.ODL_ROUTER, odl_const.ODL_ROUTERS),
                    (odl_const.ODL_PORT, odl_const.ODL_PORTS),
                    (odl_const.ODL_FLOATINGIP, odl_const.ODL_FLOATINGIPS),
                    (odl_const.ODL_LOADBALANCER, odl_const.ODL_LOADBALANCERS),
                    (odl_const.ODL_LISTENER, odl_const.ODL_LISTENERS),
                    (odl_const.ODL_POOL, odl_const.ODL_POOLS),
                    (odl_const.ODL_MEMBER, odl_const.ODL_MEMBERS),
                    (odl_const.ODL_HEALTHMONITOR,
                        odl_const.ODL_HEALTHMONITORS),
                    (odl_const.ODL_QOS_POLICY, odl_const.ODL_QOS_POLICIES),
                    (odl_const.ODL_TRUNK, odl_const.ODL_TRUNKS),
                    (odl_const.ODL_BGPVPN, odl_const.ODL_BGPVPNS),
                    (odl_const.ODL_BGPVPN_NETWORK_ASSOCIATION,
                        odl_const.ODL_BGPVPN_NETWORK_ASSOCIATIONS),
                    (odl_const.ODL_BGPVPN_ROUTER_ASSOCIATION,
                        odl_const.ODL_BGPVPN_ROUTER_ASSOCIATIONS),
                    (odl_const.ODL_SFC_FLOW_CLASSIFIER,
                        odl_const.ODL_SFC_FLOW_CLASSIFIERS),
                    (odl_const.ODL_SFC_PORT_PAIR,
                        odl_const.ODL_SFC_PORT_PAIRS),
                    (odl_const.ODL_SFC_PORT_PAIR_GROUP,
                        odl_const.ODL_SFC_PORT_PAIR_GROUPS),
                    (odl_const.ODL_SFC_PORT_CHAIN,
                        odl_const.ODL_SFC_PORT_CHAINS),
                    (odl_const.ODL_L2GATEWAY, odl_const.ODL_L2GATEWAYS),
                    (odl_const.ODL_L2GATEWAY_CONNECTION,
                        odl_const.ODL_L2GATEWAY_CONNECTIONS)]])

    def test_client_error_propagates(self):
        class TestException(Exception):
            def __init__(self):
                pass

        self._CLIENT.get.side_effect = TestException()
        self.assertRaises(TestException, full_sync.full_sync, self.db_context)

    def _mock_canary_missing(self):
        get_return = mock.MagicMock()
        get_return.status_code = requests.codes.not_found
        self._CLIENT.get.return_value = get_return

    def _assert_canary_created(self):
        rows = db.get_all_db_rows(self.db_session)
        self.assertTrue(any(r['object_uuid'] == full_sync._CANARY_NETWORK_ID
                            for r in rows))
        return rows

    def _test_full_sync_resources(self, expected_journal):
        self._mock_canary_missing()

        full_sync.full_sync(self.db_context)

        rows = self._assert_canary_created()
        rows = self._filter_out_canary(rows)
        self.assertItemsEqual(expected_journal.keys(),
                              [row['object_type'] for row in rows])
        for row in rows:
            self.assertEqual(expected_journal[row['object_type']],
                             row['object_uuid'])

    def test_full_sync_removes_pending_rows(self):
        db.create_pending_row(self.db_session, odl_const.ODL_NETWORK, "uuid",
                              odl_const.ODL_CREATE, {'foo': 'bar'})
        self._test_full_sync_resources({})

    def test_full_sync_no_resources(self):
        self._test_full_sync_resources({})

    def test_full_sync_l2_resources(self):
        full_sync.ALL_RESOURCES = {constants.CORE: mech_driver_v2.L2_RESOURCES}
        self._test_full_sync_resources(self._mock_l2_resources())

    def _mock_router_port(self, port_id):
        router_port = {'id': port_id,
                       'device_id': '1',
                       'tenant_id': '1',
                       'fixed_ips': [{'subnet_id': '1'}]}
        self.plugin.get_ports.side_effect = ([], [router_port])

    def _mock_l3_resources(self):
        expected_journal = {odl_const.ODL_ROUTER: '1',
                            odl_const.ODL_FLOATINGIP: '2'}
        self.l3_plugin.get_routers.return_value = [
            {'id': expected_journal[odl_const.ODL_ROUTER],
             'gw_port_id': None}]
        self.l3_plugin.get_floatingips.return_value = [
            {'id': expected_journal[odl_const.ODL_FLOATINGIP]}]

        return expected_journal

    def test_full_sync_l3_resources(self):
        full_sync.ALL_RESOURCES = {constants.L3: l3_odl_v2.L3_RESOURCES}
        self._test_full_sync_resources(self._mock_l3_resources())
