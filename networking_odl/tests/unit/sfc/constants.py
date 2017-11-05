# Copyright (c) 2016 Brocade Communication Systems
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

CLASSIFIERS_BASE_URI = 'sfc/flowclassifiers'
FAKE_FLOW_CLASSIFIER_ID = "4a334cd4-fe9c-4fae-af4b-321c5e2eb051"
FAKE_FLOW_CLASSIFIER = {
    "id": "4a334cd4-fe9c-4fae-af4b-321c5e2eb051",
    "name": "FC1",
    "tenant_id": "1814726e2d22407b8ca76db5e567dcf1",
    "description": "Flow rule for classifying TCP traffic",
    "protocol": "TCP",
    "source_port_range_min": 22,
    "source_port_range_max": 4000,
    "destination_port_range_min": 80,
    "destination_port_range_max": 80,
    "source_ip_prefix": "22.12.34.44",
    "destination_ip_prefix": "22.12.34.45"
}
PORT_PAIRS_BASE_URI = 'sfc/portpairs'
FAKE_PORT_PAIR_ID = "78dcd363-fc23-aeb6-f44b-56dc5e2fb3ae"
FAKE_PORT_PAIR = {
    "name": "SF1",
    "id": "78dcd363-fc23-aeb6-f44b-56dc5e2fb3ae",
    "tenant_id": "d382007aa9904763a801f68ecf065cf5",
    "description": "Firewall SF instance",
    "ingress": "dace4513-24fc-4fae-af4b-321c5e2eb3d1",
    "egress": "aef3478a-4a56-2a6e-cd3a-9dee4e2ec345"
}
PORT_PAIR_GROUPS_BASE_URI = 'sfc/portpairgroups'
FAKE_PORT_PAIR_GROUP_ID = "4512d643-24fc-4fae-af4b-321c5e2eb3d1"
FAKE_PORT_PAIR_GROUP = {
    "name": "Firewall_PortPairGroup",
    "id": "4512d643-24fc-4fae-af4b-321c5e2eb3d1",
    "tenant_id": "d382007aa9904763a801f68ecf065cf5",
    "description": "Grouping Firewall SF instances",
    "port_pairs": ["78dcd363-fc23-aeb6-f44b-56dc5e2fb3ae"]
}
PORT_CHAINS_BASE_URI = 'sfc/portchains'
FAKE_PORT_CHAIN_ID = "1278dcd4-459f-62ed-754b-87fc5e4a6751"
FAKE_PORT_CHAIN = {
    "name": "PC2",
    "id": "1278dcd4-459f-62ed-754b-87fc5e4a6751",
    "tenant_id": "d382007aa9904763a801f68ecf065cf5",
    "description": "Steering TCP and UDP traffic first to Firewall "
                   "and then to Loadbalancer",
    "flow_classifiers": ["4a334cd4-fe9c-4fae-af4b-321c5e2eb051",
                         "105a4b0a-73d6-11e5-b392-2c27d72acb4c"],
    "port_pair_groups": ["4512d643-24fc-4fae-af4b-321c5e2eb3d1",
                         "4a634d49-76dc-4fae-af4b-321c5e23d651"]
}
