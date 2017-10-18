# Copyright (c) 2015 OpenStack Foundation
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

ODL_NETWORK = 'network'
ODL_NETWORKS = 'networks'
ODL_SUBNET = 'subnet'
ODL_SUBNETS = 'subnets'
ODL_PORT = 'port'
ODL_PORTS = 'ports'
ODL_SG = 'security_group'
ODL_SGS = 'security_groups'
ODL_SG_RULE = 'security_group_rule'
ODL_SG_RULES = 'security_group_rules'
ODL_ROUTER = 'router'
ODL_ROUTERS = 'routers'
ODL_FLOATINGIP = 'floatingip'
ODL_FLOATINGIPS = 'floatingips'

ODL_LOADBALANCER = 'loadbalancer'
ODL_LOADBALANCERS = 'loadbalancers'
ODL_LISTENER = 'listener'
ODL_LISTENERS = 'listeners'
ODL_POOL = 'pool'
ODL_POOLS = 'pools'
ODL_MEMBER = 'member'
ODL_MEMBERS = 'members'
ODL_HEALTHMONITOR = 'healthmonitor'
ODL_HEALTHMONITORS = 'healthmonitors'

ODL_QOS = 'qos'
ODL_QOS_POLICY = 'policy'
ODL_QOS_POLICIES = 'policies'

ODL_SFC = 'sfc'
ODL_SFC_FLOW_CLASSIFIER = 'flowclassifier'
ODL_SFC_FLOW_CLASSIFIERS = 'flowclassifiers'
ODL_SFC_PORT_PAIR = 'portpair'
ODL_SFC_PORT_PAIRS = 'portpairs'
ODL_SFC_PORT_PAIR_GROUP = 'portpairgroup'
ODL_SFC_PORT_PAIR_GROUPS = 'portpairgroups'
ODL_SFC_PORT_CHAIN = 'portchain'
ODL_SFC_PORT_CHAINS = 'portchains'

NETWORKING_SFC_FLOW_CLASSIFIER = 'flow_classifier'
NETWORKING_SFC_FLOW_CLASSIFIERS = 'flow_classifiers'
NETWORKING_SFC_PORT_PAIR = 'port_pair'
NETWORKING_SFC_PORT_PAIRS = 'port_pairs'
NETWORKING_SFC_PORT_PAIR_GROUP = 'port_pair_group'
NETWORKING_SFC_PORT_PAIR_GROUPS = 'port_pair_groups'
NETWORKING_SFC_PORT_CHAIN = 'port_chain'
NETWORKING_SFC_PORT_CHAINS = 'port_chains'

ODL_TRUNK = 'trunk'
ODL_TRUNKS = 'trunks'

ODL_L2GATEWAY = 'l2_gateway'
ODL_L2GATEWAYS = 'l2_gateways'
ODL_L2GATEWAY_CONNECTION = 'l2gateway_connection'
ODL_L2GATEWAY_CONNECTIONS = 'l2_gateway_connections'

ODL_BGPVPN = 'bgpvpn'
ODL_BGPVPNS = 'bgpvpns'
ODL_BGPVPN_NETWORK_ASSOCIATION = 'bgpvpn_network_association'
ODL_BGPVPN_NETWORK_ASSOCIATIONS = 'bgpvpn_network_associations'
ODL_BGPVPN_ROUTER_ASSOCIATION = 'bgpvpn_router_association'
ODL_BGPVPN_ROUTER_ASSOCIATIONS = 'bgpvpn_router_associations'

ODL_ML2_MECH_DRIVER_V1 = "opendaylight"
ODL_ML2_MECH_DRIVER_V2 = "opendaylight_v2"

ODL_CREATE = 'create'
ODL_UPDATE = 'update'
ODL_DELETE = 'delete'

# Constants for journal operation states
PENDING = 'pending'
PROCESSING = 'processing'
FAILED = 'failed'
COMPLETED = 'completed'

# Journal Callback events
BEFORE_COMPLETE = 'before_complete'

# dict to store url mappings
RESOURCE_URL_MAPPINGS = {
    ODL_QOS_POLICY: "%s/%s" % (ODL_QOS, ODL_QOS_POLICIES),
    ODL_SFC_FLOW_CLASSIFIER: "%s/%s" % (ODL_SFC, ODL_SFC_FLOW_CLASSIFIERS),
    ODL_SFC_PORT_CHAIN: "%s/%s" % (ODL_SFC, ODL_SFC_PORT_CHAINS),
    ODL_SFC_PORT_PAIR: "%s/%s" % (ODL_SFC, ODL_SFC_PORT_PAIRS),
    ODL_SFC_PORT_PAIR_GROUP: "%s/%s" % (ODL_SFC, ODL_SFC_PORT_PAIR_GROUPS)
}
