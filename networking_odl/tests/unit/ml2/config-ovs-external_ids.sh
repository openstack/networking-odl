#!/bin/sh
# Copyright (c) 2016 OpenStack Foundation
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

uuid=$(sudo ovs-vsctl get Open_vSwitch . _uuid)

# Test data
sudo ovs-vsctl set Open_vSwitch $uuid \
    external_ids:odl_os_hostconfig_hostid="devstack"

# sudo ovs-vsctl set Open_vSwitch $uuid \
#    external_ids:odl_os_hostconfig_hosttype="ODL L2"

config=$(cat <<____CONFIG
{"supported_vnic_types":[
    {"vnic_type":"normal","vif_type":"ovs","vif_details":{}}],
 "allowed_network_types":["local","vlan","vxlan","gre"],
 "bridge_mappings":{"physnet1":"br-ex"}}
____CONFIG
)

echo config: $config

sudo ovs-vsctl set Open_vSwitch $uuid \
    external_ids:odl_os_hostconfig_config_odl_l2="$config"
