#!/usr/bin/env python

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


"""
Command line script to set host OVS configurations (it requires ovsctl)

Examples:
    NOTE: bash accepts new line characters between quotes

    To give a full custom json

        python set_ovs_hostconfigs.py --ovs_hostconfigs='{
                "ODL L2": {
                    "allowed_network_types":
                        ["local","vlan", "vxlan","gre"],
                    "bridge_mappings": {"physnet1":"br-ex"}
                    "supported_vnic_types": [
                        {
                            "vnic_type":"normal",
                            "vif_type":"ovs",
                            "vif_details":{}
                         }
                    ],
                },
                "ODL L3": {}
            }'

    To make sure to use system data path (Kernel)

        python set_ovs_hostconfigs.py --noovs_dpdk

    To make sure to use user space data path (vhostuser)

        python set_ovs_hostconfigs.py --ovs_dpdk

    To give bridge mappings

        python --bridge_mapping=physnet1:br-ex,physnet2:br-eth0

"""


import os
import socket
import subprocess
import sys

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils

from networking_odl._i18n import _
from networking_odl._i18n import _LE
from networking_odl._i18n import _LI
from networking_odl._i18n import _LW


LOG = log.getLogger(__name__)

USERSPACE_DATAPATH_TYPES = ['netdev', 'dpdkvhostuser']

COMMAND_LINE_OPTIONS = [

    cfg.ListOpt(
        'allowed_network_types',
        default=['local', 'vlan', 'vxlan', 'gre'],
        help=_("""
            Specifies allowed network types given as a Comma-separated list of
            types.

            Default: --allowed_network_types=local,vlan,vxlan,gre
            """)),

    cfg.DictOpt(
        'bridge_mappings',
        default={},
        help=_("""
            Comma-separated list of <physical_network>:<bridge> tuples mapping
            physical network names to the agent's node-specific Open vSwitch
            bridge names to be used for flat and VLAN networks. The length of
            bridge names should be no more than 11. Each bridge must exist, and
            should have a physical network interface configured as a port. All
            physical networks configured on the server should have mappings to
            appropriate bridges on each agent.

            Note: If you remove a bridge from this mapping, make sure to
            disconnect it from the integration bridge as it won't be managed by
            the agent anymore.

            Default: --bridge_mappings=
            """)),

    cfg.StrOpt(
        'datapath_type',
        choices=['system', 'netdev', 'dpdkvhostuser'],
        default=None,
        help=_("""
            It specifies the OVS data path to use.

            If this value is given then --ovs_dpdk will be ignored.
            If neither this option or --ovs_dpdk are given then it will use a
            valid value for current host.

            Choices: --datapath_type=
                     --datapath_type=system         # kernel data path
                     --datapath_type=netdev         # userspace data path
                     --datapath_type=dpdkvhostuser  # userspace data path

            Default: --datapath_type=netdev         # if support is detected
                     --datapath_type=system         # in all other cases
            """)),

    cfg.BoolOpt(
        'debug',
        default=False,
        help=_("""
            It shows debugging informations.

            Default: --nodebug
            """)),

    cfg.StrOpt(
        'host',
        default=socket.gethostname(),  # pylint: disable=no-member
        help=_("""
            It specifies the host name of the target machine.

            Default: --host=$HOSTNAME  # running machine host name
            """)),

    cfg.IPOpt(
        'local_ip',
        help=_("""
            IP address of local overlay (tunnel) network end-point.
            It accepts either an IPv4 or IPv6 address that resides on one
            of the host network interfaces. The IP version of this
            value must match the value of the 'overlay_ip_version'
            option in the ML2 plug-in configuration file on the Neutron
            server node(s).

            Default: local_ip=
            """)),

    cfg.BoolOpt(
        'ovs_dpdk',
        default=None,
        help=_("""
            It uses user-space type of virtual interface (vhostuser) instead of
            the system based one (ovs).

            If this option is not specified it tries to detect vhostuser
            support on running host and in case of positive match it uses it.

            NOTE: if --datapath_type is given then this option is ignored.

            Default:
            """)),

    cfg.StrOpt(
        'ovs_hostconfigs',
        help=_("""
            Fives pre-made host configuration for OpenDaylight as a JSON
            string.

            NOTE: when specified all other options are ignored!

            An entry should look like:
                --ovs_hostconfigs='{
                    "ODL L2": {
                        "allowed_network_types":
                            ["local","vlan", "vxlan","gre"],
                        "bridge_mappings": {"physnet1":"br-ex"}
                        "supported_vnic_types": [
                            {
                                "vnic_type":"normal",
                                "vif_type":"ovs",
                                "vif_details":{}
                             }
                        ],
                    },
                    "ODL L3": {}
                }'

            Default: --ovs_hostconfigs=
            """)),

    cfg.StrOpt(
        'vhostuser_mode',
        choices=['client', 'server'],
        default='client',
        help=_("""
            It specifies the OVS VHostUser mode.

            Choices: --vhostuser_mode=client
                     --vhostuser_mode=server

            Default: --vhostuser_mode=client
            """)),

    cfg.BoolOpt(
        'vhostuser_ovs_plug',
        default=True,
        help=_("""
            Enable VHostUser OVS Plug.

            Default: --vhostuser_ovs_plug
            """)),

    cfg.StrOpt(
        'vhostuser_port_prefix',
        choices=['vhu', 'socket'],
        default='vhu',
        help=_("""
            VHostUser socket port prefix.

            Choices: --vhostuser_socket_dir=vhu
                     --vhostuser_socket_dir=socket

            Default: --vhostuser_socket_dir=vhu
            """)),

    cfg.StrOpt(
        'vhostuser_socket_dir',
        default='/var/run/openvswitch',
        help=_("""
            OVS VHostUser socket directory.

            Default: --vhostuser_socket_dir=/var/run/openvswitch
            """)),
]


DEFAULT_COMMAND_LINE_OPTIONS = tuple(sys.argv[1:])


def set_ovs_extid_hostconfigs(conf, ovs_vsctl):
    if conf.ovs_hostconfigs:
        json_str = conf.ovs_hostconfigs.replace("\'", "\"")
        LOG.debug("SET-HOSTCONFIGS: JSON String %s", json_str)
        hostconfigs = jsonutils.loads(json_str)

    else:
        uuid = ovs_vsctl.uuid()
        userspace_datapath_types = ovs_vsctl.userspace_datapath_types()
        hostconfigs = _hostconfigs_from_conf(
            conf=conf, uuid=uuid,
            userspace_datapath_types=userspace_datapath_types)

    ovs_vsctl.set_host_name(conf.host)
    for name in sorted(hostconfigs):
        ovs_vsctl.set_host_config(name, hostconfigs[name])

    # for new netvirt
    if conf.local_ip:
        ovs_vsctl.set_local_ip(conf.local_ip)
    if conf.bridge_mappings:
        provider_mappings = ",".join(
            "{}:{}".format(k, v) for k, v in conf.bridge_mappings.items())
        ovs_vsctl.set_provider_mappings(provider_mappings)


def _hostconfigs_from_conf(conf, uuid, userspace_datapath_types):
    vif_type = _vif_type_from_conf(
        conf=conf, userspace_datapath_types=userspace_datapath_types)
    datapath_type = conf.datapath_type or (
        'system' if vif_type == 'ovs' else userspace_datapath_types[0])
    vif_details = _vif_details_from_conf(
        conf=conf, uuid=uuid, vif_type=vif_type)

    return {
        "ODL L2": {
            "allowed_network_types": conf.allowed_network_types,
            "bridge_mappings": conf.bridge_mappings,
            "datapath_type": datapath_type,
            "supported_vnic_types": [
                {
                    "vif_details": vif_details,
                    "vif_type": vif_type,
                    "vnic_type": "normal",
                }
            ]
        }
    }


def _vif_type_from_conf(conf, userspace_datapath_types):

    # take vif_type from datapath_type ------------------------------------
    if conf.datapath_type:
        # take it from  datapath_type
        if conf.datapath_type in USERSPACE_DATAPATH_TYPES:
            if conf.datapath_type not in userspace_datapath_types:
                LOG.warning(_LW(
                    "Using user space data path type '%s' even if no "
                    "support was detected."), conf.datapath_type)
            return 'vhostuser'
        else:
            return 'ovs'

    # take vif_type from ovs_dpdk -----------------------------------------
    if conf.ovs_dpdk is True:
        if userspace_datapath_types:
            return 'vhostuser'

        raise ValueError(_LE(
            "--ovs_dpdk option was specified but the 'netdev' datapath_type "
            "was not enabled. "
            "To override use option --datapath_type=netdev"))

    elif conf.ovs_dpdk is False:
        return 'ovs'

    # take detected dtype -------------------------------------------------
    if userspace_datapath_types:
        return 'vhostuser'
    else:
        return 'ovs'


def _vif_details_from_conf(conf, uuid, vif_type):
    host_addrasses = [conf.local_ip or conf.host]
    if vif_type == 'ovs':
        # OVS legacy mode
        return {"uuid": uuid,
                "host_addresses": host_addrasses,
                "has_datapath_type_netdev": False,
                "support_vhost_user": False}

    elif vif_type == 'vhostuser':
        # enable VHOSTUSER
        return {"uuid": uuid,
                "host_addresses": host_addrasses,
                "has_datapath_type_netdev": True,
                "support_vhost_user": True,
                "port_prefix": conf.vhostuser_port_prefix,
                "vhostuser_socket_dir": conf.vhostuser_socket_dir,
                "vhostuser_ovs_plug": conf.vhostuser_ovs_plug,
                "vhostuser_mode": conf.vhostuser_mode,
                "vhostuser_socket": os.path.join(
                    conf.vhostuser_socket_dir,
                    conf.vhostuser_port_prefix + '$PORTID')}


def setup_conf(args=None):
    """setup cmdline options."""

    if args is None:
        args = DEFAULT_COMMAND_LINE_OPTIONS

    conf = cfg.ConfigOpts()
    if '-h' in args or '--help' in args:
        # Prints out script documentation."
        print(__doc__)

    conf.register_cli_opts(COMMAND_LINE_OPTIONS)
    conf(args=args)
    return conf


class OvsVsctl(object):
    """Wrapper class for ovs-vsctl command tool

    """

    COMMAND = 'ovs-vsctl'
    TABLE = 'Open_vSwitch'

    _uuid = None

    def uuid(self):
        uuid = self._uuid
        if uuid is None:
            self._uuid = uuid = self._get('.', '_uuid')
        return uuid

    _datapath_types = None

    def datapath_types(self):
        datapath_types = self._datapath_types
        if datapath_types is None:
            try:
                datapath_types = self._get('.', 'datapath_types')
            except subprocess.CalledProcessError:
                datapath_types = 'system'
            self._datapath_types = datapath_types
        return datapath_types

    _userspace_datapath_types = None

    def userspace_datapath_types(self):
        userspace_datapath_types = self._userspace_datapath_types
        if userspace_datapath_types is None:
            datapath_types = self.datapath_types()
            userspace_datapath_types = tuple(
                datapath_type
                for datapath_type in USERSPACE_DATAPATH_TYPES
                if datapath_types.find(datapath_type) >= 0)
            self._userspace_datapath_types = userspace_datapath_types
        return userspace_datapath_types

    def set_host_name(self, host_name):
        self._set_external_ids('odl_os_hostconfig_hostid', host_name)

    def set_host_config(self, name, value):
        self._set_external_ids(
            name='odl_os_hostconfig_config_' + name.lower().replace(' ', '_'),
            value=jsonutils.dumps(value))

    def set_local_ip(self, local_ip):
        self._set_other_config("local_ip", local_ip)

    def set_provider_mappings(self, provider_mappings):
        self._set_other_config("provider_mappings", provider_mappings)

    # --- implementation details ----------------------------------------------

    def _set_external_ids(self, name, value):
        # Refer below for ovs ext-id strings
        # https://review.openstack.org/#/c/309630/
        value = 'external_ids:{}={}'.format(name, value)
        self._set(record=self.uuid(), value=value)

    def _set_other_config(self, name, value):
        value = 'other_config:{}={}'.format(name, value)
        self._set(record=self.uuid(), value=value)

    def _get(self, record, name):
        return self._excute('get', self.TABLE, record, name)

    def _set(self, record, value):
        self._excute('set', self.TABLE, record, value)

    def _excute(self, *args):
        command_line = (self.COMMAND,) + args
        LOG.info(
            _LI("SET-HOSTCONFIGS: Executing cmd: %s"), ' '.join(command_line))
        return subprocess.check_output(command_line).strip()


def main(args=None):
    """Main."""

    conf = setup_conf(args)

    if os.geteuid() != 0:
        LOG.error(_LE('Root permissions are required to configure ovsdb.'))
        return 1

    try:
        set_ovs_extid_hostconfigs(conf=conf, ovs_vsctl=OvsVsctl())

    except Exception as ex:  # pylint: disable=broad-except
        LOG.error(_LE("Fatal error: %s"), ex, exc_info=conf.debug)
        return 1

    else:
        return 0


if __name__ == '__main__':
    exit(main())
