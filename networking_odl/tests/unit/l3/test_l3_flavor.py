# Copyright (c) 2018 OpenStack Foundation
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

from neutron.objects import router as l3_obj
from oslo_config import fixture as config_fixture
from oslo_utils import uuidutils

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.l3 import l3_flavor
from networking_odl.tests import base
from networking_odl.tests.unit import base_v2

_operation_map = {'del': odl_const.ODL_DELETE,
                  'update': odl_const.ODL_UPDATE,
                  'add': odl_const.ODL_CREATE}


class OpenDaylightL3FlavorTestCase(base_v2.OpenDaylightConfigBase):
    def setUp(self):
        self.useFixture(base.OpenDaylightJournalThreadFixture())
        self.cfg = self.useFixture(config_fixture.Config())
        self.cfg.config(service_plugins=['router'])
        super(OpenDaylightL3FlavorTestCase, self).setUp()
        self.flavor_driver = l3_flavor.ODLL3ServiceProvider(mock.MagicMock())

    def _get_mock_fip_kwargs(self):
        fipid = uuidutils.generate_uuid()
        fip_db = mock.Mock(floating_ip_address='192.168.1.2',
                           router_id=None, id=fipid,
                           floating_network_id=fipid)
        projectid = uuidutils.generate_uuid()
        floating_data = {'floatingip_id': str(fipid),
                         'router_id': None,
                         'context': self.db_context,
                         'floatingip_db': fip_db,
                         'floatingip': {'project_id': str(projectid),
                                        'floating_ip_address': '172.24.5.4',
                                        'port_id': None,
                                        'id': fip_db.id,
                                        'router_id': None,
                                        'status': 'DOWN',
                                        'floating_network_id': str(fipid)
                                        }}
        return floating_data

    def _get_mock_router_kwargs(self):
        router_db = mock.Mock(gw_port_id=uuidutils.generate_uuid(),
                              id=uuidutils.generate_uuid())
        router = {odl_const.ODL_ROUTER:
                  {'name': 'router1',
                   'admin_state_up': True,
                   'tenant_id': uuidutils.generate_uuid(),
                   'id': router_db.id,
                   'external_gateway_info': {'network_id':
                                             uuidutils.generate_uuid()}},
                  'context': self.db_context,
                  "router_db": router_db}

        return router

    def _test_fip_operation(self, event, operation, fip, ops=True):
        method = getattr(self.flavor_driver,
                         '_floatingip_%s_%s' % (operation, event))
        method(odl_const.ODL_FLOATINGIP, mock.ANY, mock.ANY, **fip)
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        if ops:
            if operation != odl_const.ODL_DELETE:
                self.assertEqual(fip['floatingip'], row.data)
            self.assertEqual(odl_const.ODL_FLOATINGIP, row.object_type)
            self.assertEqual(fip['floatingip_id'], row.object_uuid)
        else:
            self.assertIsNone(row)

    def _test_router_operation(self, event, operation, router, ops=True):
        method = getattr(self.flavor_driver,
                         '_router_%s_%s' % (operation, event))
        method(odl_const.ODL_ROUTER, mock.ANY, mock.ANY, **router)
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        if ops:
            if operation in ['del', odl_const.ODL_DELETE]:
                self.assertEqual(router['router_id'], row.object_uuid)
            else:
                self.assertEqual(router['router'], row.data)
            self.assertEqual(_operation_map[operation], row.operation)
        else:
            self.assertIsNone(row)

    def test_router_add_association(self):
        with mock.patch.object(self.flavor_driver,
                               '_validate_l3_flavor',
                               return_value=True):
            router = self._get_mock_router_kwargs()
            # Driver Association payload is different and expects
            # router_id
            router['router_id'] = router['router']['id']
            self._test_router_operation("association", "add", router)

    def test_l3_operations_for_different_flavor(self):
        with mock.patch.object(self.flavor_driver,
                               '_validate_l3_flavor',
                               return_value=False):
            router = self._get_mock_router_kwargs()
            router['router_id'] = router['router']['id']
            self._test_router_operation("association", "add", router, False)
            self._test_router_operation("association", "del", router, False)

    def test_l3_router_update_precommit(self):
        with mock.patch.object(self.flavor_driver,
                               '_validate_l3_flavor',
                               return_value=True):
            router = self._get_mock_router_kwargs()
            router['router_id'] = router['router']['id']
            self._test_router_operation("precommit", "update", router)

    def test_router_del_association(self):
        with mock.patch.object(self.flavor_driver,
                               '_validate_l3_flavor',
                               return_value=True):
            router = self._get_mock_router_kwargs()
            router['router_id'] = router['router']['id']
            self._test_router_operation("association", "del", router)

    def test_fip_precommit_create(self):
        with mock.patch.object(self.flavor_driver,
                               '_validate_l3_flavor',
                               return_value=True):
            fip = self._get_mock_fip_kwargs()
            self._test_fip_operation("precommit", odl_const.ODL_CREATE, fip)

    def test_l3_fip_different_flavor(self):
        with mock.patch.object(self.flavor_driver,
                               '_validate_l3_flavor',
                               return_value=False):
            fip = self._get_mock_fip_kwargs()
            fip['old_floatingip'] = fip['floatingip']
            self._test_fip_operation("precommit",
                                     odl_const.ODL_CREATE, fip, False)
            self._test_fip_operation("precommit",
                                     odl_const.ODL_UPDATE, fip, False)

    def test_fip_precommit_delete(self):
        # As precommit delete gets port data
        fip = self._get_mock_fip_kwargs()
        port = {'port': {'id': uuidutils.generate_uuid()},
                'context': self.db_context,
                'floatingip_id': fip['floatingip_id']}
        with mock.patch.object(l3_obj.FloatingIP, 'get_objects',
                               return_value=[fip['floatingip_db']]):
            with mock.patch.object(self.flavor_driver,
                                   '_validate_l3_flavor',
                                   return_value=True):
                self._test_fip_operation("precommit",
                                         odl_const.ODL_DELETE, port)

    def test_fip_precommit_update(self):
        with mock.patch.object(self.flavor_driver,
                               '_validate_l3_flavor',
                               return_value=True):
            fip = self._get_mock_fip_kwargs()
            self._test_fip_operation("precommit", odl_const.ODL_UPDATE, fip)
