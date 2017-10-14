# Copyright Intel 2016
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

import fixtures

from neutron.agent.common import utils
from neutron.tests.common import net_helpers


class FakeMachine(fixtures.Fixture):
    """Create a fake machine.

    :ivar bridge: bridge on which the fake machine is bound
    :ivar ip_cidr: fake machine ip_cidr
    :type ip_cidr: str

    :ivar namespace: namespace emulating the machine
    :type namespace: str
    :ivar port: port binding the namespace to the bridge
    :type port: dict

    """

    def __init__(self, bridge, port):
        self.bridge = bridge
        self.port = port

    def _setUp(self):
        ns_fixture = self.useFixture(
            net_helpers.NamespaceFixture())
        self.namespace = ns_fixture.name

    def execute(self, cmds, run_as_root=True):
        ns_params = ['ip', 'netns', 'exec', self.namespace]
        cmd = ns_params + list(cmds)
        kwargs = {'run_as_root': run_as_root}
        return utils.execute(cmd, **kwargs)

    def assert_arping(self, dst_ip):
        return self.execute(
            ['arping', '-c', 3, '-I', self.interface_id, dst_ip])

    def assert_ping(self, dst_ip):
        return self.execute(['ping', '-c', 3, '-W', 1, dst_ip])

    @property
    def port_id(self):
        return self.port['port']['id']

    @property
    def interface_id(self):
        return 'ifce' + self.port_id[
            :net_helpers.OVSPortFixture.NIC_NAME_LEN - 3]

    @property
    def mac_address(self):
        return self.port['port']['mac_address']

    @property
    def ip_cidr(self):
        return self.port['port']['fixed_ips'][0]['ip_address'] + '/24'

    def set_mac_address(self):
        utils.execute(['ip', 'link', 'set', self.interface_id,
                       'netns', self.namespace],
                      run_as_root=True)

        self.execute(['ip', 'link', 'set', 'dev',
                      self.interface_id, 'address', self.mac_address])

    def set_ip_address(self):
        self.execute(['ip', 'address', 'add', self.ip_cidr,
                      'dev', self.interface_id])

    def set_dev_up(self):
        self.execute(['ip', 'link', 'set', 'dev',
                      self.interface_id, 'up'])

    def _create_ovs_vif_port(self, instance_id):
        return utils.execute(['ovs-vsctl', 'add-port', self.bridge,
                              self.interface_id, '--', 'set',
                              'Interface', self.interface_id,
                              'external-ids:iface-id=%s' % self.port_id,
                              'external-ids:iface-status=active',
                              'external-ids:attached-mac=%s'
                              % self.mac_address,
                              'external-ids:vm-uuid=%s' % instance_id,
                              'type=internal'], run_as_root=True)

    def set_address(self):
        self.set_mac_address()
        self.set_ip_address()
        self.set_dev_up()
