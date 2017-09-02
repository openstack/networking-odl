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
from networking_odl.tests.fullstack import machine


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

    def _check_device_existence(self, tap):
        def _callback():
            ports = utils.execute(
                ['ovs-vsctl', 'list-ports', 'br-int'],
                run_as_root=True)

            return bool(re.search(tap, ports))
        return test_utils.call_until_true(_callback, 30, 2)

    def _create_ovs_vif_port(self, bridge, dev, iface_id, mac, instance_id):
        return utils.execute(['ovs-vsctl', 'add-port', bridge, dev,
                              '--', 'set', 'Interface', dev,
                              'external-ids:iface-id=%s' % iface_id,
                              'external-ids:iface-status=active',
                              'external-ids:attached-mac=%s' % mac,
                              'external-ids:vm-uuid=%s' % instance_id,
                              'type=tap'], run_as_root=True)

    def _new_update_request(self, host_id, port_id):
        data = {'port': {'binding:host_id': host_id}}
        req = self.new_update_request('ports', data, port_id)
        resp = self.deserialize(self.fmt, req.get_response(self.api))
        vif_type = resp['port']['binding:vif_type']

        return vif_type

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
        vif_type = self._new_update_request(host_id, port_id)
        self.assertEqual('ovs', vif_type)
        self.assertFalse(self._check_device_existence(tap))

        # Step3: plug vif
        self._create_ovs_vif_port('br-int', tap, port_id, mac,
                                  uuidutils.generate_uuid())

        # TODO(manjeets) Add a test case to verify mac
        # in flows
        # Step4: verify device
        self.assertTrue(self._check_device_existence(tap))

    def test_VM_connectivity(self):
        # Step1: create test network
        resp = self._create_network(self.fmt, "test_fullstack_vm_net", True)
        resp = self.deserialize(self.fmt, resp)
        net_id = resp['network']['id']
        host_id = self._get_ovs_system_id()

        # Step2: create VMs and insert taps
        subnet = self._create_subnet(self.fmt, net_id, cidr='192.168.1.0/24')
        subnet = self.deserialize(self.fmt, subnet)

        fixed_ips1 = [{'ip_address': '192.168.1.1'}]
        port1 = self._create_port(self.fmt,
                                  net_id,
                                  fixed_ips=fixed_ips1)
        port1 = self.deserialize(self.fmt, port1)
        vm1 = self.useFixture(machine.FakeMachine(
            'br-int', port1))
        vif_type = self._new_update_request(host_id, port1['port']['id'])
        self.assertEqual('ovs', vif_type)
        vm1._create_ovs_vif_port(uuidutils.generate_uuid())
        vm1.set_address()

        fixed_ips2 = [{'ip_address': '192.168.1.2'}]
        port2 = self._create_port(self.fmt,
                                  net_id,
                                  fixed_ips=fixed_ips2)
        port2 = self.deserialize(self.fmt, port2)
        vm2 = self.useFixture(machine.FakeMachine(
            'br-int', port2))
        vif_type = self._new_update_request(host_id, port2['port']['id'])
        self.assertEqual('ovs', vif_type)
        vm2._create_ovs_vif_port(uuidutils.generate_uuid())
        vm2.set_address()

        # Step3: test arping
        self.assertTrue(vm1.assert_arping('192.168.1.2'))

        # Step4: test ping
        self.assertTrue(vm1.assert_ping('192.168.1.2'))
