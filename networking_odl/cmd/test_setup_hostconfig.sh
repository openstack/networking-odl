#!/bin/sh

python set_ovs_hostconfigs.py  --debug --ovs_hostconfigs='{"ODL L2": {"supported_vnic_types":[{"vnic_type":"normal", "vif_type":"ovs", "vif_details":{}}], "allowed_network_types":["local","vlan", "vxlan","gre"], "bridge_mappings":{"physnet1":"br-ex"}}, "ODL L3": {"some_details": "dummy_details"}}'
