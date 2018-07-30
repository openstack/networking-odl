# Copyright (c) 2016 OpenStack Foundation
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

from neutron.db import api as db_api

from networking_odl.common import constants as odl_const
from networking_odl.common import odl_features
from networking_odl.db import db
from networking_odl.qos import qos_driver_v2 as qos_driver
from networking_odl.tests import base
from networking_odl.tests.unit import base_v2


class OpenDaylightQosDriverTestCase(base_v2.OpenDaylightConfigBase):

    def setUp(self):
        self.useFixture(base.OpenDaylightJournalThreadFixture())
        super(OpenDaylightQosDriverTestCase, self).setUp()
        self.qos_driver = qos_driver.OpenDaylightQosDriver({})
        self.addCleanup(odl_features.deinit)

    def test_qos_supported_rules_are_fetched_from_odl_feature(self):
        feature_json = """{"features": {"feature":
                                [{"service-provider-feature":
                                "neutron-extensions:operational-port-status"},
                                {"service-provider-feature":
                                "neutron-extensions:qos-rules",
                                "configuration": {"key": "value"}}]}}"""

        self.cfg.config(odl_features_json=feature_json, group='ml2_odl')
        odl_features.init()

        qos_driver_object = qos_driver.OpenDaylightQosDriver.create()

        self.assertDictEqual(qos_driver_object.supported_rules,
                             {'key': 'value'})

    def test_default_values_for_supported_rules(self):
        self.cfg.config(odl_features='key', group='ml2_odl')
        odl_features.init()

        qos_driver_object = qos_driver.OpenDaylightQosDriver.create()

        self.assertDictEqual(qos_driver_object.supported_rules,
                             qos_driver.DEFAULT_QOS_RULES)

    def _get_mock_context(self, session=None):
        current = {'tenant_id': 'tenant_id'}
        context = mock.Mock(current=current)
        context.session = session
        return context

    def _get_mock_qos_operation_data(self):
        data = {'description': u"qos_policy",
                'rules': [],
                'tenant_id': 'test-tenant',
                'shared': False,
                'id': 'qos-policy1',
                'name': u"policy1"}
        qos_data = mock.Mock()
        to_dict = mock.Mock(return_value=data)
        qos_data.to_dict = to_dict
        return qos_data

    def _call_operation_object(self, operation, object_type):
        qos_data = self._get_mock_qos_operation_data()
        method = getattr(self.qos_driver, '%s_%s' % (operation,
                                                     object_type))

        assert object_type.endswith("precommit")
        with db_api.context_manager.writer.using(self.db_context):
            context = self._get_mock_context(self.db_context.session)
            method(context, qos_data)

    def _test_qos_policy(self, operation):
        self._call_operation_object(operation=operation,
                                    object_type='policy_precommit')
        qos_data = self._get_mock_qos_operation_data()
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        self.assertEqual(operation, row['operation'])
        self.assertEqual(qos_data.to_dict()['id'], row['object_uuid'])

    def test_qos_policy_create(self):
        self._test_qos_policy(odl_const.ODL_CREATE)

    def test_qos_policy_update(self):
        self._test_qos_policy(odl_const.ODL_UPDATE)

    def test_qos_policy_delete(self):
        self._test_qos_policy(odl_const.ODL_DELETE)
