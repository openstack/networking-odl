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

import subprocess

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils

from neutron._i18n import _
from neutron._i18n import _LE
from neutron._i18n import _LI
from neutron.common import config

LOG = log.getLogger(__name__)


class SetOvsHostconfigs(object):

    # Refer below for ovs ext-id strings
    # https://review.openstack.org/#/c/309630/
    extid_str = 'external_ids:{}={}'
    odl_os_hconf_str = 'odl_os_hostconfig_config_{}'
    odl_os_hostid_str = 'odl_os_hostconfig_hostid'
    odl_os_hosttype_str = 'odl_os_hostconfig_hosttype'

    # TODO(mzmalick): use neutron.agent.ovsdb instead of subprocess.Popen
    ovs_cmd_get_uuid = ['ovs-vsctl', 'get', 'Open_vSwitch', '.', '_uuid']
    ovs_cmd_set_extid = ['ovs-vsctl', 'set', 'Open_vSwitch', '', '']

    UUID = 3
    EXTID = 4

    def __init__(self):
        self.ovs_uuid = self.get_ovs_uuid()

    def subprocess_exec(self, cmd):
        LOG.info(_LI("SET-HOSTCONFIGS: Executing cmd: %s"), ' '.join(cmd))
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

    def get_ovs_uuid(self):
        return self.subprocess_exec(self.ovs_cmd_get_uuid)[0].strip()

    def set_extid_hostname(self, hname):
        self.ovs_cmd_set_extid[self.UUID] = self.ovs_uuid
        self.ovs_cmd_set_extid[self.EXTID] = self.extid_str.format(
            self.odl_os_hostid_str, hname)
        return self.subprocess_exec(self.ovs_cmd_set_extid)

    def set_extid_hosttype(self, htype):
        self.ovs_cmd_set_extid[self.UUID] = self.ovs_uuid
        self.ovs_cmd_set_extid[self.EXTID] = self.extid_str.format(
            self.odl_os_hosttype_str, htype)
        return self.subprocess_exec(self.ovs_cmd_set_extid)

    def set_extid_hostconfig(self, htype, hconfig):
        ext_htype = self.odl_os_hconf_str.format(
            htype.lower().replace(' ', '_'))
        self.ovs_cmd_set_extid[self.UUID] = self.ovs_uuid
        self.ovs_cmd_set_extid[self.EXTID] = self.extid_str.format(
            ext_htype, hconfig)
        return self.subprocess_exec(self.ovs_cmd_set_extid)

    def set_ovs_extid_hostconfigs(self, conf):
        if not conf.ovs_hostconfigs:
            LOG.error(_LE("ovs_hostconfigs argument needed!"))
            return

        json_str = cfg.CONF.ovs_hostconfigs
        json_str.replace("\'", "\"")
        LOG.debug("SET-HOSTCONFIGS: JSON String %s", json_str)

        self.set_extid_hostname(cfg.CONF.host)
        htype_config = jsonutils.loads(json_str)

        for htype in htype_config.keys():
            self.set_extid_hostconfig(htype, htype_config[htype])


def setup_conf():
    """setup cmdline options."""
    cli_opts = [
        cfg.StrOpt('ovs_hostconfigs', help=_(
            "OVS hostconfiguration for OpenDaylight "
            "as a JSON string"))
    ]

    conf = cfg.CONF
    conf.register_cli_opts(cli_opts)
    conf.import_opt('host', 'neutron.common.config')
    conf()
    return conf


def main():

    conf = setup_conf()
    config.setup_logging()
    SetOvsHostconfigs().set_ovs_extid_hostconfigs(conf)

#
# command line example (run without line breaks):
#
# set_ovs_hostconfigs.py  --ovs_hostconfigs='{"ODL L2": {
# "supported_vnic_types":[{"vnic_type":"normal", "vif_type":"ovs",
# "vif_details":{}}], "allowed_network_types":["local","vlan",
# "vxlan","gre"], "bridge_mappings":{"physnet1":"br-ex"}},
# "ODL L3": {}}' --debug
#

if __name__ == '__main__':
    main()
