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

from neutron_lib.callbacks import events
from neutron_lib.callbacks import resources
from neutron_lib import constants as n_const
from neutron_lib.plugins import directory

from neutron.services.trunk import callbacks
from neutron.services.trunk import constants as trunk_consts
from neutron.services.trunk import models

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.tests.unit import base_v2
from networking_odl.trunk import trunk_driver_v2 as trunk_driver


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
    'updated_at': '2016-11-16T10:17:44Z',
    'revision_number': 2,
    'project_id': 'fake_project_id',
    'port_id': 'fake_port_id',
    'id': 'fake_id',
    'description': 'fake trunk port'}

FAKE_PARENT = {
    'id': 'fake_parent_id',
    'tenant_id': 'fake_tenant_id',
    'name': 'parent_port',
    'admin_state_up': 'true',
    'status': 'ACTIVE'}


class TestTrunkHandler(base_v2.OpenDaylightConfigBase):
    def setUp(self):
        super(TestTrunkHandler, self).setUp()
        self.handler = (trunk_driver.
                        OpenDaylightTrunkHandlerV2())

    def _fake_trunk_payload(self):
        payload = callbacks.TrunkPayload(
            self.db_context, 'fake_id',
            mock.Mock(return_value=FAKE_TRUNK),
            mock.Mock(return_value=FAKE_TRUNK),
            mock.Mock(return_value=FAKE_TRUNK['sub_ports']))
        payload.current_trunk.status = trunk_consts.DOWN_STATUS
        payload.current_trunk.to_dict = mock.Mock(return_value=FAKE_TRUNK)
        payload.original_trunk.status = trunk_consts.DOWN_STATUS
        payload.original_trunk.to_dict = mock.Mock(return_value=FAKE_TRUNK)
        return payload

    def _call_operation_object(self, operation, timing, fake_payload):
        method = getattr(self.handler, 'trunk_%s_%s' % (operation, timing))
        method(mock.ANY, mock.ANY, mock.ANY, fake_payload)

    def _test_event(self, operation, timing):
        fake_payload = self._fake_trunk_payload()
        self._call_operation_object(operation, timing, fake_payload)
        if timing == 'precommit':
            self.db_session.flush()

        row = db.get_oldest_pending_db_row_with_lock(self.db_session)

        if timing == 'precommit':
            self.assertEqual(operation, row['operation'])
            self.assertEqual(odl_const.ODL_TRUNK, row['object_type'])
            self.assertEqual(fake_payload.trunk_id, row['object_uuid'])
        elif timing == 'after':
            self.assertIsNone(row)

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

    @mock.patch.object(trunk_driver.OpenDaylightTrunkHandlerV2,
                       '_set_subport_status')
    def test_trunk_subports_set_status_create_parent_active(
            self, mock_set_subport_status):
        resource = trunk_consts.SUBPORTS
        event_type = events.AFTER_CREATE
        fake_payload = self._fake_trunk_payload()
        core_plugin = directory.get_plugin()

        fake_payload.subports = [models.SubPort(port_id='fake_port_id',
                                                segmentation_id=101,
                                                segmentation_type='vlan',
                                                trunk_id='fake_id')]
        parent_port = FAKE_PARENT

        with mock.patch.object(core_plugin, '_get_port') as gp:
            gp.return_value = parent_port
            self.handler.trunk_subports_set_status(resource, event_type,
                                                   mock.ANY, fake_payload)
            mock_set_subport_status.assert_called_once_with(
                core_plugin, mock.ANY, 'fake_port_id',
                n_const.PORT_STATUS_ACTIVE)

    @mock.patch.object(trunk_driver.OpenDaylightTrunkHandlerV2,
                       '_set_subport_status')
    def test_trunk_subports_set_status_create_parent_down(
            self, mock_set_subport_status):
        resource = trunk_consts.SUBPORTS
        event_type = events.AFTER_CREATE
        fake_payload = self._fake_trunk_payload()
        core_plugin = directory.get_plugin()

        fake_payload.subports = [models.SubPort(port_id='fake_port_id',
                                                segmentation_id=101,
                                                segmentation_type='vlan',
                                                trunk_id='fake_id')]
        parent_port = FAKE_PARENT.copy()
        parent_port['status'] = n_const.PORT_STATUS_DOWN

        with mock.patch.object(core_plugin, '_get_port') as gp:
            gp.return_value = parent_port
            self.handler.trunk_subports_set_status(resource, event_type,
                                                   mock.ANY, fake_payload)
            mock_set_subport_status.assert_called_once_with(
                core_plugin, mock.ANY, 'fake_port_id',
                n_const.PORT_STATUS_DOWN)

    @mock.patch.object(trunk_driver.OpenDaylightTrunkHandlerV2,
                       '_set_subport_status')
    def test_trunk_subports_set_status_delete(self, mock_set_subport_status):
        resource = trunk_consts.SUBPORTS
        event_type = events.AFTER_DELETE
        fake_payload = self._fake_trunk_payload()

        fake_payload.subports = [models.SubPort(port_id='fake_port_id',
                                                segmentation_id=101,
                                                segmentation_type='vlan',
                                                trunk_id='fake_id')]

        self.handler.trunk_subports_set_status(resource, event_type, mock.ANY,
                                               fake_payload)
        mock_set_subport_status.assert_called_once_with(
            mock.ANY, mock.ANY, 'fake_port_id', n_const.PORT_STATUS_DOWN)

    @mock.patch.object(trunk_driver.OpenDaylightTrunkHandlerV2,
                       '_get_subports_ids')
    @mock.patch.object(trunk_driver.OpenDaylightTrunkHandlerV2,
                       '_set_subport_status')
    def test_trunk_subports_update_status_parent_down_to_active(
            self, mock_set_subport_status, mock_get_subports_ids):
        resource = resources.PORT
        event_type = events.AFTER_UPDATE
        core_plugin = directory.get_plugin()
        port = FAKE_PARENT.copy()
        original_port = FAKE_PARENT.copy()
        original_port['status'] = n_const.PORT_STATUS_DOWN
        port_kwargs = {'port': port, 'original_port': original_port}

        mock_get_subports_ids.return_value = ['fake_port_id']

        self.handler.trunk_subports_update_status(resource, event_type,
                                                  mock.ANY, **port_kwargs)

        mock_set_subport_status.assert_called_once_with(
            core_plugin, mock.ANY, 'fake_port_id', n_const.PORT_STATUS_ACTIVE)

    @mock.patch.object(trunk_driver.OpenDaylightTrunkHandlerV2,
                       '_get_subports_ids')
    @mock.patch.object(trunk_driver.OpenDaylightTrunkHandlerV2,
                       '_set_subport_status')
    def test_trunk_subports_update_status_parent_active_to_down(
            self, mock_set_subport_status, mock_get_subports_ids):
        resource = resources.PORT
        event_type = events.AFTER_UPDATE
        core_plugin = directory.get_plugin()
        port = FAKE_PARENT.copy()
        original_port = FAKE_PARENT.copy()
        port['status'] = n_const.PORT_STATUS_DOWN
        port_kwargs = {'port': port, 'original_port': original_port}

        mock_get_subports_ids.return_value = ['fake_port_id']

        self.handler.trunk_subports_update_status(resource, event_type,
                                                  mock.ANY, **port_kwargs)

        mock_set_subport_status.assert_called_once_with(
            core_plugin, mock.ANY, 'fake_port_id', n_const.PORT_STATUS_DOWN)


class TestTrunkDriver(base_v2.OpenDaylightConfigBase):
    def setUp(self):
        super(TestTrunkDriver, self).setUp()

    def test_is_loaded(self):
        driver = trunk_driver.OpenDaylightTrunkDriverV2.create()
        self.cfg.config(mechanism_drivers=["logger",
                                           odl_const.ODL_ML2_MECH_DRIVER_V2],
                        group='ml2')
        self.assertTrue(driver.is_loaded)

        self.cfg.config(mechanism_drivers=['logger'], group='ml2')
        self.assertFalse(driver.is_loaded)

        self.cfg.config(core_plugin='some_plugin')
        self.assertFalse(driver.is_loaded)
