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

# pylint: disable=unused-argument, protected-access


from contextlib import contextmanager
import os
import sys
import tempfile

import mock
from oslo_serialization import jsonutils
import six

from networking_odl.cmd import set_ovs_hostconfigs
from networking_odl.tests import base
from networking_odl.tests import match

LOGGING_ENABLED = "Logging Enabled!"
LOGGING_PERMISSION_REQUIRED = "permissions are required to configure ovsdb"


@contextmanager
def capture(command, args):
    out, sys.stdout = sys.stdout, six.StringIO()
    try:
        command(args)
        sys.stdout.seek(0)
        yield sys.stdout.read()
    finally:
        sys.stdout = out


class TestSetOvsHostconfigs(base.DietTestCase):

    maxDiff = None

    def test_given_ovs_hostconfigs(self):
        # given
        self.patch_os_geteuid()
        ovs_hostconfigs = {
            "ODL L2": {"allowed_network_types": ["a", "b", "c"]}}
        args = ['--ovs_hostconfigs=' + jsonutils.dumps(ovs_hostconfigs),
                '--bridge_mappings=a:1,b:2']
        execute = self.patch_utils_execute()
        conf = set_ovs_hostconfigs.setup_conf(args)

        # when
        result = set_ovs_hostconfigs.main(args)

        # then
        self.assertEqual(0, result)
        execute.assert_has_calls([
            mock.call(
                ('ovs-vsctl', 'get', 'Open_vSwitch', '.', '_uuid')),
            mock.call(
                ('ovs-vsctl', 'set', 'Open_vSwitch', '<some-uuid>',
                 'external_ids:odl_os_hostconfig_hostid=' + conf.host)),
            mock.call(
                ('ovs-vsctl', 'set', 'Open_vSwitch', '<some-uuid>',
                 match.wildcard(
                     'external_ids:odl_os_hostconfig_config_odl_l2=*'))),
        ])

        expected = ovs_hostconfigs['ODL L2']
        _, actual_json = execute.call_args_list[2][0][0][4].split("=", 1)
        self.assertEqual(match.json(expected), actual_json)

    def test_given_no_args(self):
        self._test_given_args(tuple())

    def test_given_default_values(self):
        self._test_given_args([])

    def test_given_datapath_type_system(self):
        self._test_given_args(['--datapath_type=netdev'])

    def test_given_datapath_type_netdev(self):
        self._test_given_args(['--datapath_type=netdev'])

    def test_given_datapath_type_vhostuser(self):
        self._test_given_args(['--datapath_type=dpdkvhostuser'])

    def test_given_ovs_dpdk(self):
        self._test_given_args(['--ovs_dpdk'])

    def test_given_noovs_dpdk(self):
        self._test_given_args(['--noovs_dpdk'])

    def test_given_ovs_sriov_offload(self):
        self._test_given_args(['--noovs_dpdk', '--ovs_sriov_offload'])

    def test_given_vhostuser_ovs_plug(self):
        self._test_given_args(['--vhostuser_ovs_plug'])

    def test_given_novhostuser_ovs_plug(self):
        self._test_given_args(['--novhostuser_ovs_plug'])

    def test_given_allowed_network_types(self):
        self._test_given_args(['--allowed_network_types=a,b,c'])

    def test_given_local_ip(self):
        self._test_given_args(['--local_ip=192.168.1.10', '--host='])

    def test_given_vhostuser_mode_server(self):
        self._test_given_args(
            ['--vhostuser_mode=server', '--datapath_type=netdev'])

    def test_given_vhostuser_mode_client(self):
        self._test_given_args(
            ['--vhostuser_mode=client', '--datapath_type=netdev'])

    def test_given_vhostuser_port_prefix_vhu(self):
        self._test_given_args(
            ['--vhostuser_port_prefix=vhu', '--datapath_type=netdev'])

    def test_given_vhostuser_port_prefix_socket(self):
        self._test_given_args(
            ['--vhostuser_port_prefix=socket', '--datapath_type=netdev'])

    def test_given_config_file(self):
        file_descriptor, file_path = tempfile.mkstemp()

        try:
            os.write(file_descriptor, six.b("# dummy neutron config file\n"))
            os.close(file_descriptor)
            self._test_given_args(['--config-file={}'.format(file_path)])

        finally:
            os.remove(file_path)

    def _test_given_args(self, *args):
        # given
        self.patch_os_geteuid()
        execute = self.patch_utils_execute()
        conf = set_ovs_hostconfigs.setup_conf(*args)

        datapath_type = conf.datapath_type
        if datapath_type is None:
            if conf.ovs_dpdk is False:
                datapath_type = "system"
            else:
                datapath_type = "netdev"

        # when
        result = set_ovs_hostconfigs.main(*args)

        # then
        self.assertEqual(0, result)
        execute.assert_has_calls([
            mock.call(
                ('ovs-vsctl', 'get', 'Open_vSwitch', '.', '_uuid')),
            mock.call(
                ('ovs-vsctl', 'get', 'Open_vSwitch', '.', 'datapath_types')),
            mock.call(
                ('ovs-vsctl', 'set', 'Open_vSwitch', '<some-uuid>',
                 'external_ids:odl_os_hostconfig_hostid=' + conf.host)),
            mock.call(
                ('ovs-vsctl', 'set', 'Open_vSwitch', '<some-uuid>',
                 match.wildcard(
                     'external_ids:odl_os_hostconfig_config_odl_l2=*'))),
        ])

        host_addresses = [conf.host or conf.local_ip]
        if datapath_type == "system":
            vif_type = "ovs"
            vif_details = {
                "uuid": '<some-uuid>',
                "host_addresses": host_addresses,
                "has_datapath_type_netdev": False,
                "support_vhost_user": False
            }
        else:  # datapath_type in ["system", "netdev"]
            vif_type = "vhostuser"
            vif_details = {
                "uuid": '<some-uuid>',
                "host_addresses": host_addresses,
                "has_datapath_type_netdev": True,
                "support_vhost_user": True,
                "port_prefix": conf.vhostuser_port_prefix,
                "vhostuser_mode": conf.vhostuser_mode,
                "vhostuser_ovs_plug": conf.vhostuser_ovs_plug,
                "vhostuser_socket_dir": conf.vhostuser_socket_dir,
                "vhostuser_socket": os.path.join(
                    conf.vhostuser_socket_dir,
                    conf.vhostuser_port_prefix + "$PORT_ID"),
            }

        _, actual_json = execute.call_args_list[3][0][0][4].split("=", 1)
        expected = {
            "allowed_network_types": conf.allowed_network_types,
            "bridge_mappings": conf.bridge_mappings,
            "datapath_type": datapath_type,
            "supported_vnic_types": [
                {
                    "vif_type": vif_type,
                    "vnic_type": "normal",
                    "vif_details": vif_details
                }
            ]
        }

        if vif_type == 'ovs' and conf.ovs_sriov_offload:
            direct_vnic = {
                "vif_details": vif_details,
                "vif_type": vif_type,
                "vnic_type": "direct",
            }
            expected["supported_vnic_types"].append(direct_vnic)
        self.assertEqual(match.json(expected), actual_json)

    def test_given_ovs_dpdk_undetected(self):
        # given
        LOG = self.patch(set_ovs_hostconfigs, 'LOG')
        args = ('--ovs_dpdk', '--bridge_mappings=a:1,b:2', '--debug')
        conf = set_ovs_hostconfigs.setup_conf(args)
        self.patch_os_geteuid()
        execute = self.patch_utils_execute(datapath_types="whatever")

        # when
        result = set_ovs_hostconfigs.main(args)

        # then
        self.assertEqual(1, result)
        execute.assert_has_calls([
            mock.call(
                ('ovs-vsctl', 'get', 'Open_vSwitch', '.', '_uuid')),
            mock.call(
                ('ovs-vsctl', 'get', 'Open_vSwitch', '.', 'datapath_types')),
        ])
        LOG.error.assert_called_once_with(
            "Fatal error: %s",
            match.wildcard(
                "--ovs_dpdk option was specified but the 'netdev' "
                "datapath_type was not enabled. To override use option "
                "--datapath_type=netdev"), exc_info=conf.debug)

    def test_bridge_mappings(self):
        # when
        conf = set_ovs_hostconfigs.setup_conf(('--bridge_mappings=a:1,b:2',))
        self.assertEqual({'a': '1', 'b': '2'}, conf.bridge_mappings)

    def test_allowed_network_types(self):
        # when
        conf = set_ovs_hostconfigs.setup_conf(('--allowed_network_types=a,b',))
        self.assertEqual(['a', 'b'], conf.allowed_network_types)

    def patch_utils_execute(
            self, uuid='<some-uuid>',
            datapath_types='netdev,dpdkvhostuser,system'):

        def execute(args):
            command, method, table, record, value = args
            self.assertEqual('ovs-vsctl', command)
            self.assertEqual('Open_vSwitch', table)
            self.assertIn(method, ['get', 'set'])
            if method == 'set':
                self.assertEqual(uuid, record)
                return ""
            elif method == 'get':
                self.assertEqual('.', record)
                self.assertIn(value, ['_uuid', 'datapath_types'])
                if value == '_uuid':
                    return uuid
                elif value == 'datapath_types':
                    return datapath_types

            self.fail('Unexpected command: ' + repr(args))

        return self.patch(
            set_ovs_hostconfigs.subprocess, "check_output",
            side_effect=execute)

    def patch_os_geteuid(self, return_value=0):
        return self.patch(
            set_ovs_hostconfigs.os, "geteuid", return_value=return_value)

    @contextmanager
    def test_log_on_console_msg(self):
        with capture(set_ovs_hostconfigs.main, args=()) as output:
            self.assertNotEqual(-1, output.find(LOGGING_PERMISSION_REQUIRED))

    def test_log_in_file(self):
        with tempfile.TemporaryFile() as fp:
            set_ovs_hostconfigs.main(("--log-file=%s" % fp.name,))
            logs = [LOGGING_ENABLED, LOGGING_PERMISSION_REQUIRED]
            for line, count in fp.readline():
                self.assertNotEqual(-1, line.find(logs[count]))
