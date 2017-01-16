# Copyright (c) 2017 Ericsson India Global Service Pvt Ltd.
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


from neutron.db import api as neutron_db_api

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.tests.unit import base_v2
from networking_odl.trunk import trunk_driver_v2 as trunk_driver

from neutron.services.trunk import callbacks
from neutron.services.trunk import constants as trunk_consts

from oslo_config import cfg

FAKE_TRUNK = {
    'status': 'ACTIVE',
    'sub_ports': [{'segmentation_type': 'vlan',
                   'port_id': 'fake_port_id',
                   'segmentation_id': 101},
                  {'segmentation_type': 'vlan',
                   'port_id': 'fake_port_id',
                   'segmentation_id': 102}],
    'name': 'trunk0',
    'admin_state_up': 'true',
    'tenant_id': 'fake_tenant_id',
    'created_at': '2016-11-16T10:17:32Z',
    'updated_at': '2016-11-16T10:17:44Z',
    'revision_number': 2,
    'project_id': 'fake_project_id',
    'port_id': 'fake_port_id',
    'id': 'fake_id',
    'description': 'fake trunk port'}


class TestTrunkHandler(base_v2.OpenDaylightConfigBase):
    def setUp(self):
        super(TestTrunkHandler, self).setUp()
        self.db_session = neutron_db_api.get_session()
        self.handler = (trunk_driver.
                        OpenDaylightTrunkHandlerV2())

    def _get_mock_context(self):
        context = mock.Mock()
        context.session = self.db_session
        return context

    def _fake_trunk_payload(self):
        payload = callbacks.TrunkPayload(
            self._get_mock_context(), 'fake_id',
            mock.Mock(return_value=FAKE_TRUNK),
            mock.Mock(return_value=FAKE_TRUNK),
            mock.Mock(return_value=FAKE_TRUNK['sub_ports']))
        payload.current_trunk.status = trunk_consts.DOWN_STATUS
        payload.current_trunk.to_dict = mock.Mock(return_value=FAKE_TRUNK)
        payload.original_trunk.status = trunk_consts.DOWN_STATUS
        payload.original_trunk.to_dict = mock.Mock(return_value=FAKE_TRUNK)
        return payload

    def _call_operation_object(self, operation, timing):
        fake_payload = self._fake_trunk_payload()
        method = getattr(self.handler, 'trunk_%s_%s' % (operation, timing))
        method(mock.ANY, mock.ANY, mock.ANY, fake_payload)

    def _test_event(self, operation, timing):
        self._call_operation_object(operation, timing)
        fake_payload = self._fake_trunk_payload()
        row = db.get_oldest_pending_db_row_with_lock(self.db_session)

        if timing == 'precommit':
            self.assertEqual(operation, row['operation'])
            self.assertEqual(odl_const.ODL_TRUNK, row['object_type'])
            self.assertEqual(fake_payload.trunk_id, row['object_uuid'])
        elif timing == 'after':
            self.assertEqual(None, row)

    def test_trunk_create_precommit(self):
        self._test_event("create", "precommit")

    def test_trunk_create_postcommit(self):
        self._test_event("create", "postcommit")

    def test_trunk_update_precommit(self):
        self._test_event("update", "precommit")

    def test_trunk_update_postcommit(self):
        self._test_event("update", "postcommit")

    def test_trunk_delete_precommit(self):
        self._test_event("delete", "precommit")

    def test_trunk_delete_postcommit(self):
        self._test_event("delete", "postcommit")


class TestTrunkDriver(base_v2.OpenDaylightConfigBase):
    def setUp(self):
        super(TestTrunkDriver, self).setUp()

    def test_is_loaded(self):
        driver = trunk_driver.OpenDaylightTrunkDriverV2.create()
        cfg.CONF.set_override('mechanism_drivers',
                              ["logger", odl_const.ODL_ML2_MECH_DRIVER_V2],
                              group='ml2')
        self.assertTrue(driver.is_loaded)

        cfg.CONF.set_override('mechanism_drivers',
                              ['logger'],
                              group='ml2')
        self.assertFalse(driver.is_loaded)

        cfg.CONF.set_override('core_plugin', 'some_plugin')
        self.assertFalse(driver.is_loaded)
