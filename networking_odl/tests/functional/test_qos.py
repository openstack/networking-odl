# Copyright (C) 2017 Intel Corporation.
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

import contextlib

from oslo_utils import uuidutils

from neutron.extensions import qos as qos_ext
from neutron.services.qos import qos_plugin
from neutron.tests.unit.api import test_extensions
from neutron.tests.unit.plugins.ml2 import test_plugin
from neutron_lib import fixture as nlib_fixture
from neutron_lib.plugins import directory

from networking_odl.common import constants as odl_const
from networking_odl.tests.functional import base


class QoSTestExtensionManager(object):

    def get_resources(self):
        return qos_ext.Qos.get_resources()

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


class _QoSDriverTestCase(base.OdlTestsBase):

    def test_policy_create(self):
        with self.qos_policy() as policy:
            self.assert_resource_created(
                odl_const.ODL_QOS_POLICY, policy)

    def test_policy_update(self):
        with self.qos_policy() as policy:
            self.resource_update_test(
                odl_const.ODL_QOS_POLICY, policy)

    def test_policy_delete(self):
        with self.qos_policy() as policy:
            self.resource_delete_test(
                odl_const.ODL_QOS_POLICY, policy)


class QoSDriverTests(base.V2DriverAdjustment,
                     _QoSDriverTestCase,
                     test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']

    def setUp(self):
        self.useFixture(nlib_fixture.PluginDirectoryFixture())
        super(QoSDriverTests, self).setUp()
        self.qos_plug = qos_plugin.QoSPlugin()
        directory.add_plugin('QOS', self.qos_plug)
        ext_mgr = QoSTestExtensionManager()
        self.resource_prefix_map = {'policies': '/qos'}
        self.ext_api = test_extensions.setup_extensions_middleware(ext_mgr)
        tenant_id = uuidutils.generate_uuid()
        self.policy_data = {
            'policy': {'name': 'test-policy', 'tenant_id': tenant_id}}

    @contextlib.contextmanager
    def qos_policy(self, fmt='json'):
        po_res = self.new_create_request('policies', self.policy_data, fmt)
        po_rep = po_res.get_response(self.ext_api)
        policy = self.deserialize(fmt, po_rep)
        yield policy
