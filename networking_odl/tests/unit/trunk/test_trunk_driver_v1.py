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

from neutron.services.trunk import callbacks
from neutron.services.trunk import constants as trunk_consts
from neutron.tests import base as base_test
from neutron_lib.callbacks import events
from oslo_config import fixture as config_fixture


from networking_odl.common.client import OpenDaylightRestClient as client
from networking_odl.common import constants as odl_const
from networking_odl.tests import base as odl_base
from networking_odl.trunk import trunk_driver_v1 as trunk_driver


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


class TestTrunkHandler(base_test.BaseTestCase):
    def setUp(self):
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        super(TestTrunkHandler, self).setUp()
        self.handler = (trunk_driver.
                        OpenDaylightTrunkHandlerV1())

    def _fake_trunk_event_payload(self):
        payload = callbacks.TrunkPayload(
            mock.Mock(), 'fake_id',
            mock.Mock(return_value=FAKE_TRUNK),
            mock.Mock(return_value=FAKE_TRUNK),
            mock.Mock(return_value=FAKE_TRUNK['sub_ports']))
        payload.current_trunk.status = trunk_consts.DOWN_STATUS
        payload.current_trunk.to_dict = mock.Mock(return_value=FAKE_TRUNK)
        payload.original_trunk.status = trunk_consts.DOWN_STATUS
        payload.original_trunk.to_dict = mock.Mock(return_value=FAKE_TRUNK)
        return payload

    @mock.patch.object(client, 'sendjson')
    def test_create_trunk(self, mocked_sendjson):
        fake_payload = self._fake_trunk_event_payload()
        expected = {odl_const.ODL_TRUNK: fake_payload.current_trunk.to_dict()}
        self.handler.trunk_event(mock.ANY, events.AFTER_CREATE,
                                 mock.ANY, fake_payload)
        mocked_sendjson.assert_called_once_with('post', odl_const.ODL_TRUNKS,
                                                expected)

    @mock.patch.object(client, 'sendjson')
    def test_update_trunk(self, mocked_sendjson):
        fake_payload = self._fake_trunk_event_payload()
        expected = {odl_const.ODL_TRUNK: fake_payload.current_trunk.to_dict()}
        self.handler.trunk_event(mock.ANY, events.AFTER_UPDATE,
                                 mock.ANY, fake_payload)
        url = odl_const.ODL_TRUNKS + '/' + fake_payload.trunk_id
        mocked_sendjson.assert_called_once_with('put', url, expected)

    @mock.patch.object(client, 'sendjson')
    def test_subport(self, mocked_sendjson):
        fake_payload = self._fake_trunk_event_payload()
        expected = {odl_const.ODL_TRUNK: fake_payload.current_trunk.to_dict()}
        self.handler.subport_event(mock.ANY, mock.ANY, mock.ANY, fake_payload)
        url = odl_const.ODL_TRUNKS + '/' + fake_payload.trunk_id
        mocked_sendjson.assert_called_once_with('put', url, expected)

    @mock.patch.object(client, 'try_delete')
    def test_delete_trunk(self, mocked_try_delete):
        fake_payload = self._fake_trunk_event_payload()
        self.handler.trunk_event(mock.ANY, events.AFTER_DELETE,
                                 mock.ANY, fake_payload)
        url = odl_const.ODL_TRUNKS + '/' + fake_payload.trunk_id
        mocked_try_delete.assert_called_once_with(url)


class TestTrunkDriver(base_test.BaseTestCase):
    def setUp(self):
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        super(TestTrunkDriver, self).setUp()

    def test_is_loaded(self):
        driver = trunk_driver.OpenDaylightTrunkDriverV1.create()
        self.cfg = self.useFixture(config_fixture.Config())
        self.cfg.config(mechanism_drivers=["logger",
                                           odl_const.ODL_ML2_MECH_DRIVER_V1],
                        group='ml2')
        self.assertTrue(driver.is_loaded)

        self.cfg.config(mechanism_drivers=['logger'], group='ml2')
        self.assertFalse(driver.is_loaded)

        self.cfg.config(core_plugin='some_plugin')
        self.assertFalse(driver.is_loaded)
