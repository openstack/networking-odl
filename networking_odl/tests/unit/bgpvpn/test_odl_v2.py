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

from networking_odl.bgpvpn import odl_v2 as driverv2
from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.tests.unit import base_v2


class OpenDaylightBgpvpnDriverTestCase(base_v2.OpenDaylightConfigBase):

    def setUp(self):
        super(OpenDaylightBgpvpnDriverTestCase, self).setUp()
        self.driver = driverv2.OpenDaylightBgpvpnDriver(service_plugin=None)

    def _get_fake_bgpvpn(self, net=False, router=False):
        net_id = []
        router_id = []
        if router:
            router_id = ['ROUTER_ID']
        if net:
            net_id = ['NET_ID']
        fake_bgpvpn = {'route_targets': '100:1',
                       'route_distinguishers': ['100:1'],
                       'id': 'BGPVPN_ID',
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
        rows = sorted(db.get_all_db_rows_by_state(self.db_context,
                                                  odl_const.PENDING),
                      key=lambda x: x.seqnum)
        if precommit:
            self.db_context.session.flush()
            self.assertEqual(operation, rows[0]['operation'])
            self.assertEqual(object_type, rows[0]['object_type'])
            self.assertEqual(data['id'], rows[0]['object_uuid'])
        else:
            self.assertEqual([], rows)

    def test_create_bgpvpn(self):
        fake_data = self._get_fake_bgpvpn()
        self.driver.create_bgpvpn_precommit(self.db_context, fake_data)
        self._assert_op(odl_const.ODL_CREATE, odl_const.ODL_BGPVPN,
                        fake_data)
        self.run_journal_processing()
        self._assert_op(odl_const.ODL_CREATE, odl_const.ODL_BGPVPN,
                        fake_data, False)

    def test_update_bgpvpn(self):
        fake_data = self._get_fake_bgpvpn()
        self.driver.update_bgpvpn_precommit(self.db_context, fake_data)
        self._assert_op(odl_const.ODL_UPDATE, odl_const.ODL_BGPVPN,
                        fake_data)
        self.run_journal_processing()
        self._assert_op(odl_const.ODL_UPDATE, odl_const.ODL_BGPVPN,
                        fake_data, False)

    def test_delete_bgpvpn(self):
        fake_data = self._get_fake_bgpvpn()
        self.driver.delete_bgpvpn_precommit(self.db_context, fake_data)
        self._assert_op(odl_const.ODL_DELETE, odl_const.ODL_BGPVPN,
                        fake_data)
        self.run_journal_processing()
        self._assert_op(odl_const.ODL_DELETE, odl_const.ODL_BGPVPN,
                        fake_data, False)

    def test_create_router_assoc(self):
        fake_rtr_assoc_data = self._get_fake_router_assoc()
        fake_rtr_upd_bgpvpn_data = self._get_fake_bgpvpn(router=True)
        with mock.patch.object(self.driver, 'get_router_assocs',
                               return_value=[]), \
            mock.patch.object(self.driver, 'get_bgpvpn',
                              return_value=fake_rtr_upd_bgpvpn_data):
            self.driver.create_router_assoc_precommit(self.db_context,
                                                      fake_rtr_assoc_data)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_rtr_upd_bgpvpn_data)
            self.run_journal_processing()
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_rtr_upd_bgpvpn_data, False)

    def test_delete_router_assoc(self):
        fake_rtr_assoc_data = self._get_fake_router_assoc()
        fake_bgpvpn_data = self._get_fake_bgpvpn(router=True)
        with mock.patch.object(self.driver, 'get_bgpvpn',
                               return_value=fake_bgpvpn_data):
            self.driver.delete_router_assoc_precommit(self.db_context,
                                                      fake_rtr_assoc_data)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_bgpvpn_data)
            self.run_journal_processing()
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_bgpvpn_data, False)

    def test_create_net_assoc(self):
        fake_net_assoc_data = self._get_fake_net_assoc()
        fake_net_upd_bgpvpn_data = self._get_fake_bgpvpn(net=True)
        # todo(vivekanandan) add check for case when assoc already exists
        with mock.patch.object(self.driver, 'get_bgpvpns',
                               return_value=[fake_net_upd_bgpvpn_data]):
            self.driver.create_net_assoc_precommit(self.db_context,
                                                   fake_net_assoc_data)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_net_upd_bgpvpn_data)
            self.run_journal_processing()
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_net_upd_bgpvpn_data, False)

    def test_delete_net_assoc(self):
        fake_net_assoc_data = self._get_fake_net_assoc()
        fake_bgpvpn_data = self._get_fake_bgpvpn(net=True)
        with mock.patch.object(self.driver, 'get_bgpvpn',
                               return_value=fake_bgpvpn_data):
            self.driver.delete_net_assoc_precommit(self.db_context,
                                                   fake_net_assoc_data)
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_bgpvpn_data)
            self.run_journal_processing()
            self._assert_op(odl_const.ODL_UPDATE,
                            odl_const.ODL_BGPVPN,
                            fake_bgpvpn_data, False)
