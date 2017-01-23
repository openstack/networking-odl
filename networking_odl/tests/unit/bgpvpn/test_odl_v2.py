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

import mock

from neutron.db import api as neutron_db_api

from networking_odl.bgpvpn import odl_v2 as driverv2
from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.journal import journal
from networking_odl.tests.unit import base_v2


class OpendaylightBgpvpnDriverTestCase(base_v2.OpenDaylightConfigBase):

    def setUp(self):
        super(OpendaylightBgpvpnDriverTestCase, self).setUp()
        self.db_session = neutron_db_api.get_reader_session()
        self.driver = driverv2.OpenDaylightBgpvpnDriver(service_plugin=None)
        self.context = self._get_mock_context()
        self.mock_sync_thread = mock.patch.object(
            journal.OpendaylightJournalThread, 'start_odl_sync_thread').start()
        self.thread = journal.OpendaylightJournalThread()

    def _get_mock_context(self):
        context = mock.Mock()
        context.session = self.db_session
        return context

    def _get_fake_bgpvpn(self, net=False, router=False):
        net_id = []
        router_id = []
        if router:
            router_id = ['ROUTER_ID']
        if net:
            net_id = ['NET_ID']
        fake_bgpvpn = {'export_targets': mock.ANY, 'name': mock.ANY,
                       'route_targets': '100:1', 'tenant_id': mock.ANY,
                       'project_id': mock.ANY,
                       'import_targets': mock.ANY,
                       'route_distinguishers': ['100:1'],
                       'type': mock.ANY, 'id': 'BGPVPN_ID',
                       'networks': net_id,
                       'routers': router_id}
        return fake_bgpvpn

    def _get_fake_router_assoc(self):
        fake_router_assoc = {'id': 'ROUTER_ASSOC_ID',
                             'bgpvpn_id': 'BGPVPN_ID',
                             'router_id': 'ROUTER_ID'}
        return fake_router_assoc

    def _get_fake_net_assoc(self):
        fake_net_assoc = {'id': 'NET_ASSOC_ID',
                          'bgpvpn_id': 'BGPVPN_ID',
                          'network_id': 'NET_ID'}
        return fake_net_assoc

    def _assert_op(self, operation, object_type, data, precommit=True):
        rows = sorted(db.get_all_db_rows_by_state(self.db_session,
                                                  odl_const.PENDING),
                      key=lambda x: x.seqnum)
        if precommit:
            self.assertEqual(operation, rows[0]['operation'])
            self.assertEqual(object_type, rows[0]['object_type'])
            self.assertEqual(data['id'], rows[0]['object_uuid'])
        else:
            self.assertEqual([], rows)

    def test_create_bgpvpn(self):
        fake_data = self._get_fake_bgpvpn()
        self.driver.create_bgpvpn_precommit(self.context, fake_data)
        self._assert_op(odl_const.ODL_CREATE, odl_const.ODL_BGPVPN,
                        fake_data)
        self.thread.run_sync_thread(exit_after_run=True)
        self._assert_op(odl_const.ODL_CREATE, odl_const.ODL_BGPVPN,
                        fake_data, False)

    def test_update_bgpvpn(self):
        fake_data = self._get_fake_bgpvpn()
        self.driver.update_bgpvpn_precommit(self.context, fake_data)
        self._assert_op(odl_const.ODL_UPDATE, odl_const.ODL_BGPVPN,
                        fake_data)
        self.thread.run_sync_thread(exit_after_run=True)
        self._assert_op(odl_const.ODL_UPDATE, odl_const.ODL_BGPVPN,
                        fake_data, False)

    def test_delete_bgpvpn(self):
        fake_data = self._get_fake_bgpvpn()
        self.driver.delete_bgpvpn_postcommit(self.context, fake_data)
        self.thread.run_sync_thread(exit_after_run=True)
        self._assert_op(odl_const.ODL_DELETE, odl_const.ODL_BGPVPN,
                        fake_data, False)

    def test_create_router_assoc(self):
        fake_rtr_assoc_data = self._get_fake_router_assoc()
        fake_rtr_upd_bgpvpn_data = self._get_fake_bgpvpn(router=True)
        with mock.patch.object(self.driver, 'get_router_assocs',
                               return_value=[]), \
            mock.patch.object(self.driver, 'get_bgpvpn',
                              return_value=fake_rtr_upd_bgpvpn_data):
            self.driver.create_router_assoc_precommit(self.context,
                                                      fake_rtr_assoc_data)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_rtr_upd_bgpvpn_data)
            self.thread.run_sync_thread(exit_after_run=True)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_rtr_upd_bgpvpn_data, False)

    def test_delete_router_assoc(self):
        fake_rtr_assoc_data = self._get_fake_router_assoc()
        fake_bgpvpn_data = self._get_fake_bgpvpn(router=False)
        with mock.patch.object(self.driver, 'get_bgpvpn',
                               return_value=fake_bgpvpn_data):
            self.driver.delete_router_assoc_postcommit(self.context,
                                                       fake_rtr_assoc_data)
            self.thread.run_sync_thread(exit_after_run=True)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_bgpvpn_data, False)

    def test_create_net_assoc(self):
        fake_net_assoc_data = self._get_fake_net_assoc()
        fake_net_upd_bgpvpn_data = self._get_fake_bgpvpn(net=True)
        # todo(vivekanandan) add check for case when assoc already exists
        with mock.patch.object(self.driver, 'get_bgpvpns',
                               return_value=[fake_net_upd_bgpvpn_data]):
            self.driver.create_net_assoc_precommit(self.context,
                                                   fake_net_assoc_data)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_net_upd_bgpvpn_data)
            self.thread.run_sync_thread(exit_after_run=True)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_net_upd_bgpvpn_data, False)

    def test_delete_net_assoc(self):
        fake_net_assoc_data = self._get_fake_net_assoc()
        fake_bgpvpn_data = self._get_fake_bgpvpn(net=False)
        with mock.patch.object(self.driver, 'get_bgpvpn',
                               return_value=fake_bgpvpn_data):
            self.driver.delete_net_assoc_postcommit(self.context,
                                                    fake_net_assoc_data)
            self.thread.run_sync_thread(exit_after_run=True)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_bgpvpn_data, False)
