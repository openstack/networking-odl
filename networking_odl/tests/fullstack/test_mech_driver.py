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

import re

from oslo_utils import uuidutils
from tempest.lib.common.utils import test_utils

from neutron.agent.common import utils
from neutron.tests.common import net_helpers

from networking_odl.tests.fullstack import base


class TestMechDriver(base.TestODLFullStackBase):

    def setUp(self):
        super(TestMechDriver, self).setUp()

    def _get_ovs_system_id(self):
        # Example:
        # ('{system-id="f1487b2f-b103-4ce0-b4ab-1a94258405dd"}\n', '')
        system_id = utils.execute(['ovs-vsctl', 'get', 'Open_Vswitch',
                                   '.', 'external_ids'],
                                  run_as_root=True)
        return re.findall('".*"', system_id)[0]

    def _check_flow_existance(self, mac):
        def _callback():
            flows = utils.execute(
                ['ovs-appctl', 'bridge/dump-flows', 'br-int'],
                run_as_root=True)

            return bool(re.search(mac, flows))
        return test_utils.call_until_true(_callback, 30, 2)

    def _create_ovs_vif_port(self, bridge, dev, iface_id, mac, instance_id):
        return utils.execute(['ovs-vsctl', 'add-port', bridge, dev,
                              '--', 'set', 'Interface', dev,
                              'external-ids:iface-id=%s' % iface_id,
                              'external-ids:iface-status=active',
                              'external-ids:attached-mac=%s' % mac,
                              'external-ids:vm-uuid=%s' % instance_id,
                              'type=tap'], run_as_root=True)

    def test_port_plugging(self):
        # Step1: create test network
        resp = self._create_network(self.fmt, "test_fullstack_net", True)
        resp = self.deserialize(self.fmt, resp)
        net_id = resp['network']['id']

        # Step2: create port and binding to host
        host_id = self._get_ovs_system_id()
        resp = self._create_port(self.fmt, net_id)
        resp = self.deserialize(self.fmt, resp)
        port_id = resp['port']['id']
        mac = resp['port']['mac_address']
        tap = 'tap' + port_id[:net_helpers.OVSPortFixture.NIC_NAME_LEN - 3]
        data = {'port': {'binding:host_id': host_id}}
        req = self.new_update_request('ports', data, port_id)
        resp = self.deserialize(self.fmt, req.get_response(self.api))
        vif_type = resp['port']['binding:vif_type']
        self.assertEqual('ovs', vif_type)
        self.assertFalse(self._check_flow_existance(mac))

        # Step3: plug vif
        self._create_ovs_vif_port('br-int', tap, port_id, mac,
                                  uuidutils.generate_uuid())

        # Step4: verify flow table
        self.assertTrue(self._check_flow_existance(mac))
