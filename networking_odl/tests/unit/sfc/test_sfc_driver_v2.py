# Copyright (c) 2017 Brocade Communication Systems
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

from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.sfc import sfc_driver_v2 as sfc
from networking_odl.tests import base as odl_base
from networking_odl.tests.unit import base_v2
from networking_odl.tests.unit.sfc import constants as sfc_const


class TestOpenDaylightSFCDriverV2(base_v2.OpenDaylightConfigBase):
    def setUp(self):
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        super(TestOpenDaylightSFCDriverV2, self).setUp()
        self.handler = sfc.OpenDaylightSFCDriverV2()
        self.handler.initialize()

    def _get_mock_portpair_operation_context(self):
        mocked_fc_context = patch(
            'networking_sfc.services.sfc.common.context.PortPairContext'
        ).start().return_value

        mocked_fc_context.current = sfc_const.FAKE_PORT_PAIR
        mocked_fc_context.session = self.db_session
        mocked_fc_context._plugin_context = mocked_fc_context
        return mocked_fc_context

    def _get_mock_portpairgroup_operation_context(self):
        mocked_fc_context = patch(
            'networking_sfc.services.sfc.common.context.PortPairGroupContext'
        ).start().return_value

        mocked_fc_context.current = sfc_const.FAKE_PORT_PAIR_GROUP
        mocked_fc_context.session = self.db_session
        mocked_fc_context._plugin_context = mocked_fc_context
        return mocked_fc_context

    def _get_mock_portchain_operation_context(self):
        mocked_fc_context = patch(
            'networking_sfc.services.sfc.common.context.PortChainContext'
        ).start().return_value

        mocked_fc_context.current = sfc_const.FAKE_PORT_CHAIN
        mocked_fc_context.session = self.db_session
        mocked_fc_context._plugin_context = mocked_fc_context
        return mocked_fc_context

    def _get_mock_operation_context(self, object_type):
        getter = getattr(self, '_get_mock_%s_operation_context' % object_type)
        return getter()

    def _call_operation_object(self, operation, timing, resource_str, context):
        method = getattr(self.handler,
                         '%s_%s_%s' % (operation, resource_str, timing))
        method(context)

    def _test_event(self, operation, timing, resource_str,
                    object_type):
        context = self._get_mock_operation_context(object_type)
        self._call_operation_object(operation, timing, resource_str, context)
        if timing == 'precommit':
            self.db_session.flush()
        row = db.get_oldest_pending_db_row_with_lock(self.db_session)

        if timing == 'precommit':
            self.assertEqual(operation, row['operation'])
            self.assertEqual(object_type, row['object_type'])
        elif timing == 'after':
            self.assertIsNone(row)

    # TODO(yamahata): utilize test scenarios
    def test_create_port_pair_precommit(self):
        self._test_event("create", "precommit", "port_pair",
                         odl_const.ODL_SFC_PORT_PAIR)

    def test_create_port_pair_postcommit(self):
        self._test_event("create", "postcommit", "port_pair",
                         odl_const.ODL_SFC_PORT_PAIR)

    def test_update_port_pair_precommit(self):
        self._test_event("update", "precommit", "port_pair",
                         odl_const.ODL_SFC_PORT_PAIR)

    def test_update_port_pair_postcommit(self):
        self._test_event("update", "postcommit", "port_pair",
                         odl_const.ODL_SFC_PORT_PAIR)

    def test_delete_port_pair_precommit(self):
        self._test_event("delete", "precommit", "port_pair",
                         odl_const.ODL_SFC_PORT_PAIR)

    def test_delete_port_pair_postcommit(self):
        self._test_event("delete", "postcommit", "port_pair",
                         odl_const.ODL_SFC_PORT_PAIR)

    def test_create_port_pair_group_precommit(self):
        self._test_event("create", "precommit", "port_pair_group",
                         odl_const.ODL_SFC_PORT_PAIR_GROUP)

    def test_create_port_pair_group_postcommit(self):
        self._test_event("create", "postcommit", "port_pair_group",
                         odl_const.ODL_SFC_PORT_PAIR_GROUP)

    def test_update_port_pair_group_precommit(self):
        self._test_event("update", "precommit", "port_pair_group",
                         odl_const.ODL_SFC_PORT_PAIR_GROUP)

    def test_update_port_pair_group_postcommit(self):
        self._test_event("update", "postcommit", "port_pair_group",
                         odl_const.ODL_SFC_PORT_PAIR_GROUP)

    def test_delete_port_pair_group_precommit(self):
        self._test_event("delete", "precommit", "port_pair_group",
                         odl_const.ODL_SFC_PORT_PAIR_GROUP)

    def test_delete_port_pair_group_postcommit(self):
        self._test_event("delete", "postcommit", "port_pair_group",
                         odl_const.ODL_SFC_PORT_PAIR_GROUP)

    def test_create_port_chain_precommit(self):
        self._test_event("create", "precommit", "port_chain",
                         odl_const.ODL_SFC_PORT_CHAIN)

    def test_create_port_chain_postcommit(self):
        self._test_event("create", "postcommit", "port_chain",
                         odl_const.ODL_SFC_PORT_CHAIN)

    def test_update_port_chain_precommit(self):
        self._test_event("update", "precommit", "port_chain",
                         odl_const.ODL_SFC_PORT_CHAIN)

    def test_update_port_chain_postcommit(self):
        self._test_event("update", "postcommit", "port_chain",
                         odl_const.ODL_SFC_PORT_CHAIN)

    def test_delete_port_chain_precommit(self):
        self._test_event("delete", "precommit", "port_chain",
                         odl_const.ODL_SFC_PORT_CHAIN)

    def test_delete_port_chain_postcommit(self):
        self._test_event("delete", "postcommit", "port_chain",
                         odl_const.ODL_SFC_PORT_CHAIN)
