# Copyright (c) 2016 OpenStack Foundation
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

from neutron.tests import base as base_test

from networking_odl.common import constants as odl_const
from networking_odl.qos import qos_driver
from networking_odl.qos import qos_utils
from networking_odl.tests import base as odl_base

FAKE_POLICY = {'description': 'qos_policy',
               'rules': [{'max_kpbs': 30,
                          'type': 'bandwidth_limit',
                          'id': 'test-id',
                          'max_burst_kpbs': 0,
                          'qos_policy_id': 'fake_id'},
                         {'dscp_mark': 12,
                          'type': 'dscp_marking',
                          'id': 'test-id2',
                          'qos_policy_id': 'fake-id2'}],
               'tenant_id': 'fake_tenant',
               'shared': 'false',
               'id': 'fake_id',
               'name': 'fake_policy'}


class MakeObjectofDictionary(object):
    def __init__(self, **entries):
            self.__dict__.update(entries)

    def to_dict(self):
        return self.__dict__


class OpenDaylightQosDriverTestCase(base_test.BaseTestCase):

    def setUp(self):
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        super(OpenDaylightQosDriverTestCase, self).setUp()
        self._qos_driver = qos_driver.OpenDaylightQosDriver()
        self.context = mock.Mock(current=FAKE_POLICY.copy())

    def _test_send_resource(self, operation, method, data):
        with mock.patch.object(self._qos_driver, "send_resource") as res:
            getattr(self._qos_driver, method)(
                self.context,
                MakeObjectofDictionary(**data))

        res.assert_called_once_with(
            operation,
            odl_const.ODL_QOS_POLICIES,
            data)

    def test_qos_policy_create(self):
        self._test_send_resource(odl_const.ODL_CREATE,
                                 'create_policy',
                                 FAKE_POLICY)

    def test_qos_policy_delete(self):
        self._test_send_resource(odl_const.ODL_DELETE,
                                 'delete_policy',
                                 FAKE_POLICY)

    def test_qos_policy_update(self):
        self._test_send_resource(odl_const.ODL_UPDATE,
                                 'update_policy',
                                 FAKE_POLICY)

    def test_qos_policy_update_without_rules(self):
        policy = {'description': 'qos_policy',
                  'tenant_id': 'fake_tenant',
                  'shared': 'false',
                  'id': 'fake_id',
                  'name': 'fake_policy'}
        self._test_send_resource(odl_const.ODL_UPDATE,
                                 'update_policy',
                                 policy)

    def test_format_policy_rules(self):
        policy = qos_utils.convert_rules_format(FAKE_POLICY)
        self.assertIn("bandwidth_limit_rules", policy)
        self.assertIn("dscp_marking_rules", policy)
