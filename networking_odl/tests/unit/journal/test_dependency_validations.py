#
# Copyright (C) 2016 Intel Corp. Isaku Yamahata <isaku.yamahata@gmail com>
# All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#

import testscenarios

from networking_odl.common import constants as const
from networking_odl.db import db
from networking_odl.journal import dependency_validations
from networking_odl.tests.unit import test_base_db


load_tests = testscenarios.load_tests_apply_scenarios


_NET_ID = 'NET_ID'
_NET_DATA = {'id': _NET_ID}
_SUBNET_ID = 'SUBNET_ID'
_SUBNET_DATA = {'network_id': _NET_ID}
_PORT_ID = 'PORT_ID'
_PORT_DATA = {'network_id': _NET_ID,
              'fixed_ips': [{'subnet_id': _SUBNET_ID}]}
_PORT_DATA_DUPLICATE_SUBNET = {
    'network_id': _NET_ID,
    'fixed_ips': [{'subnet_id': _SUBNET_ID},
                  {'subnet_id': _SUBNET_ID}]
}
_ROUTER_ID = 'ROUTER_ID'
_ROUTER_DATA = {'id': 'ROUTER_ID',
                'gw_port_id': 'GW_PORT_ID'}
_L2GW_ID = 'l2gw_id'
_L2GW_DATA = {'id': _L2GW_ID}
_L2GWCONN_ID = 'l2gwconn_id'
_L2GWCONN_DATA = {'id': _L2GWCONN_ID,
                  'network_id': _NET_ID,
                  'gateway_id': _L2GW_ID}
_TRUNK_ID = 'TRUNK_ID'
_SUBPORT_ID = 'CPORT_ID'
_TRUNK_DATA = {'trunk_id': _TRUNK_ID,
               'port_id': _PORT_ID,
               'sub_ports': [{'port_id': _SUBPORT_ID}]}
_BGPVPN_ID = 'BGPVPN_ID'
_SG_ID = 'SG_ID'
_SG_DATA = {'id': _SG_ID}
_SG_RULE_ID = 'SG_RULE_ID'
_SG_RULE_DATA = {'id': _SG_RULE_ID,
                 'security_group_id': _SG_ID}


def get_data(res_type, operation):
    if res_type == const.ODL_NETWORK:
        return [_NET_DATA]
    elif res_type == const.ODL_SUBNET:
        if operation == const.ODL_DELETE:
            return [[_NET_ID]]
        return [_SUBNET_DATA]
    elif res_type == const.ODL_PORT:
        # TODO(yamahata): test case of (ODL_port, ODL_DELETE) is missing
        if operation == const.ODL_DELETE:
            return [[_NET_ID, _SUBNET_ID]]
        return [_PORT_DATA, _PORT_DATA_DUPLICATE_SUBNET]
    elif res_type == const.ODL_ROUTER:
        return [_ROUTER_DATA]
    elif res_type == const.ODL_L2GATEWAY:
        return [_L2GW_DATA]
    elif res_type == const.ODL_L2GATEWAY_CONNECTION:
        return [_L2GWCONN_DATA]
    elif res_type == const.ODL_TRUNK:
        if operation == const.ODL_DELETE:
            return [[_PORT_ID, _SUBPORT_ID]]
        return [_TRUNK_DATA]
    elif res_type == const.ODL_BGPVPN:
        if operation == const.ODL_DELETE:
            return [[_NET_ID, _ROUTER_ID]]
        else:
            routers = []
            networks = []
            if operation == const.ODL_UPDATE:
                routers = [_ROUTER_ID]
                networks = [_NET_ID]
            return [{'id': _BGPVPN_ID, 'networks': networks,
                     'routers': routers,
                     'route_distinguishers': ['100:1']}]
    elif res_type == const.ODL_SG:
        return [_SG_DATA]
    elif res_type == const.ODL_SG_RULE:
        if operation == const.ODL_DELETE:
            return [[_SG_RULE_ID]]
        return [_SG_RULE_DATA]
    return [[]]


def subnet_fail_network_dep(net_op, subnet_op):
    return {'expected': 1,
            'first_type': const.ODL_NETWORK,
            'first_operation': net_op,
            'first_id': _NET_ID,
            'second_type': const.ODL_SUBNET,
            'second_operation': subnet_op,
            'second_id': _SUBNET_ID}


def subnet_succeed_network_dep(net_op, subnet_op):
    return {'expected': 0,
            'first_type': const.ODL_SUBNET,
            'first_operation': subnet_op,
            'first_id': _SUBNET_ID,
            'second_type': const.ODL_NETWORK,
            'second_operation': net_op,
            'second_id': _NET_ID}


# TODO(vthapar) add tests for l2gw dependency validations
class BaseDependencyValidationsTestCase(object):
    def test_dependency(self):
        db.create_pending_row(
            self.db_session, self.first_type, self.first_id,
            self.first_operation,
            get_data(self.first_type, self.first_operation))
        for data in get_data(self.second_type, self.second_operation):
            deps = dependency_validations.calculate(
                self.db_session, self.second_operation, self.second_type,
                self.second_id, data)
            self.assertEqual(self.expected, len(deps))


class SubnetDependencyValidationsTestCase(
        test_base_db.ODLBaseDbTestCase, BaseDependencyValidationsTestCase):
    scenarios = (
        ("subnet_create_depends_on_older_network_create",
         subnet_fail_network_dep(const.ODL_CREATE, const.ODL_CREATE)),
        ("subnet_create_depends_on_older_network_update",
         subnet_fail_network_dep(const.ODL_UPDATE, const.ODL_CREATE)),
        ("subnet_create_depends_on_older_network_delete",
         subnet_fail_network_dep(const.ODL_DELETE, const.ODL_CREATE)),
        ("subnet_create_doesnt_depend_on_newer_network_create",
         subnet_succeed_network_dep(const.ODL_CREATE, const.ODL_CREATE)),
        ("subnet_create_doesnt_depend_on_newer_network_update",
         subnet_succeed_network_dep(const.ODL_UPDATE, const.ODL_CREATE)),
        ("subnet_create_doesnt_depend_on_newer_network_delete",
         subnet_succeed_network_dep(const.ODL_DELETE, const.ODL_CREATE)),
        ("subnet_update_depends_on_older_network_create",
         subnet_fail_network_dep(const.ODL_CREATE, const.ODL_UPDATE)),
        ("subnet_update_depends_on_older_network_update",
         subnet_fail_network_dep(const.ODL_UPDATE, const.ODL_UPDATE)),
        ("subnet_update_depends_on_older_network_delete",
         subnet_fail_network_dep(const.ODL_DELETE, const.ODL_UPDATE)),
        ("subnet_update_doesnt_depend_on_newer_network_create",
         subnet_succeed_network_dep(const.ODL_CREATE, const.ODL_UPDATE)),
        ("subnet_update_doesnt_depend_on_newer_network_update",
         subnet_succeed_network_dep(const.ODL_UPDATE, const.ODL_UPDATE)),
        ("subnet_update_doesnt_depend_on_newer_network_delete",
         subnet_succeed_network_dep(const.ODL_DELETE, const.ODL_UPDATE)),
        ("subnet_delete_doesnt_depend_on_older_network_create",
         subnet_succeed_network_dep(const.ODL_CREATE, const.ODL_DELETE)),
        ("subnet_delete_doesnt_depend_on_older_network_update",
         subnet_succeed_network_dep(const.ODL_UPDATE, const.ODL_DELETE)),
        ("subnet_delete_doesnt_depend_on_newer_network_create",
         subnet_succeed_network_dep(const.ODL_CREATE, const.ODL_DELETE)),
        ("subnet_delete_doesnt_depend_on_newer_network_update",
         subnet_succeed_network_dep(const.ODL_UPDATE, const.ODL_DELETE)),
    )


def security_rule_fail_security_group_dep(sg_op, sgr_op):
    return {'expected': 1,
            'first_type': const.ODL_SG,
            'first_operation': sg_op,
            'first_id': _SG_ID,
            'second_type': const.ODL_SG_RULE,
            'second_operation': sgr_op,
            'second_id': _SG_RULE_ID}


def security_rule_succeed_security_group_dep(sg_op, sgr_op):
    return {'expected': 0,
            'first_type': const.ODL_SG_RULE,
            'first_operation': sgr_op,
            'first_id': _SG_RULE_ID,
            'second_type': const.ODL_SG,
            'second_operation': sg_op,
            'second_id': _SG_ID}


class SecurityRuleDependencyValidationsTestCase(
        test_base_db.ODLBaseDbTestCase, BaseDependencyValidationsTestCase):
    scenarios = (
        ("security_rule_create_depends_on_older_security_group_create",
         security_rule_fail_security_group_dep(const.ODL_CREATE,
                                               const.ODL_CREATE)),
        ("security_rule_create_depends_on_older_security_group_update",
         security_rule_fail_security_group_dep(const.ODL_UPDATE,
                                               const.ODL_CREATE)),
        ("security_rule_create_depends_on_older_security_group_delete",
         security_rule_fail_security_group_dep(const.ODL_DELETE,
                                               const.ODL_CREATE)),
        ("security_rule_create_doesnt_depend_on_newer_security_group_create",
         security_rule_succeed_security_group_dep(const.ODL_CREATE,
                                                  const.ODL_CREATE)),
        ("security_rule_create_doesnt_depend_on_newer_security_group_update",
         security_rule_succeed_security_group_dep(const.ODL_UPDATE,
                                                  const.ODL_CREATE)),
        ("security_rule_create_doesnt_depend_on_newer_security_group_delete",
         security_rule_succeed_security_group_dep(const.ODL_DELETE,
                                                  const.ODL_CREATE)),
        ("security_rule_update_depends_on_older_security_group_create",
         security_rule_fail_security_group_dep(const.ODL_CREATE,
                                               const.ODL_UPDATE)),
        ("security_rule_update_depends_on_older_security_group_update",
         security_rule_fail_security_group_dep(const.ODL_UPDATE,
                                               const.ODL_UPDATE)),
        ("security_rule_update_depends_on_older_security_group_delete",
         security_rule_fail_security_group_dep(const.ODL_DELETE,
                                               const.ODL_UPDATE)),
        ("security_rule_update_doesnt_depend_on_newer_security_group_create",
         security_rule_succeed_security_group_dep(const.ODL_CREATE,
                                                  const.ODL_UPDATE)),
        ("security_rule_update_doesnt_depend_on_newer_security_group_update",
         security_rule_succeed_security_group_dep(const.ODL_UPDATE,
                                                  const.ODL_UPDATE)),
        ("security_rule_update_doesnt_depend_on_newer_security_group_delete",
         security_rule_succeed_security_group_dep(const.ODL_DELETE,
                                                  const.ODL_UPDATE)),
        ("security_rule_delete_doesnt_depend_on_older_security_group_create",
         security_rule_succeed_security_group_dep(const.ODL_CREATE,
                                                  const.ODL_DELETE)),
        ("security_rule_delete_doesnt_depend_on_older_security_group_update",
         security_rule_succeed_security_group_dep(const.ODL_UPDATE,
                                                  const.ODL_DELETE)),
        ("security_rule_delete_doesnt_depend_on_newer_security_group_create",
         security_rule_succeed_security_group_dep(const.ODL_CREATE,
                                                  const.ODL_DELETE)),
        ("security_rule_delete_doesnt_depend_on_newer_security_group_update",
         security_rule_succeed_security_group_dep(const.ODL_UPDATE,
                                                  const.ODL_DELETE)),
    )


def port_fail_network_dep(net_op, port_op):
    return {'expected': 1,
            'first_type': const.ODL_NETWORK,
            'first_operation': net_op,
            'first_id': _NET_ID,
            'second_type': const.ODL_PORT,
            'second_operation': port_op,
            'second_id': _PORT_ID}


def port_succeed_network_dep(net_op, port_op):
    return {'expected': 0,
            'first_type': const.ODL_PORT,
            'first_operation': port_op,
            'first_id': _PORT_ID,
            'second_type': const.ODL_NETWORK,
            'second_operation': net_op,
            'second_id': _NET_ID}


def port_fail_subnet_dep(subnet_op, port_op):
    return {'expected': 1,
            'first_type': const.ODL_SUBNET,
            'first_operation': subnet_op,
            'first_id': _SUBNET_ID,
            'second_type': const.ODL_PORT,
            'second_operation': port_op,
            'second_id': _PORT_ID}


def port_succeed_subnet_dep(subnet_op, port_op):
    return {'expected': 0,
            'first_type': const.ODL_PORT,
            'first_operation': port_op,
            'first_id': _PORT_ID,
            'second_type': const.ODL_SUBNET,
            'second_operation': subnet_op,
            'second_id': _SUBNET_ID}


class PortDependencyValidationsTestCase(
        test_base_db.ODLBaseDbTestCase, BaseDependencyValidationsTestCase):
    scenarios = (
        ("port_create_depends_on_older_network_create",
         port_fail_network_dep(const.ODL_CREATE, const.ODL_CREATE)),
        ("port_create_depends_on_older_network_update",
         port_fail_network_dep(const.ODL_UPDATE, const.ODL_CREATE)),
        ("port_create_depends_on_older_network_delete",
         port_fail_network_dep(const.ODL_DELETE, const.ODL_CREATE)),
        ("port_create_doesnt_depend_on_newer_network_create",
         port_succeed_network_dep(const.ODL_CREATE, const.ODL_CREATE)),
        ("port_create_doesnt_depend_on_newer_network_update",
         port_succeed_network_dep(const.ODL_UPDATE, const.ODL_CREATE)),
        ("port_create_doesnt_depend_on_newer_network_delete",
         port_succeed_network_dep(const.ODL_DELETE, const.ODL_CREATE)),
        ("port_update_depends_on_older_network_create",
         port_fail_network_dep(const.ODL_CREATE, const.ODL_UPDATE)),
        ("port_update_depends_on_older_network_update",
         port_fail_network_dep(const.ODL_UPDATE, const.ODL_UPDATE)),
        ("port_update_depends_on_older_network_delete",
         port_fail_network_dep(const.ODL_DELETE, const.ODL_UPDATE)),
        ("port_update_doesnt_depend_on_newer_network_create",
         port_succeed_network_dep(const.ODL_CREATE, const.ODL_UPDATE)),
        ("port_update_doesnt_depend_on_newer_network_update",
         port_succeed_network_dep(const.ODL_UPDATE, const.ODL_UPDATE)),
        ("port_update_doesnt_depend_on_newer_network_delete",
         port_succeed_network_dep(const.ODL_DELETE, const.ODL_UPDATE)),
        ("port_create_depends_on_older_subnet_create",
         port_fail_subnet_dep(const.ODL_CREATE, const.ODL_CREATE)),
        ("port_create_depends_on_older_subnet_update",
         port_fail_subnet_dep(const.ODL_UPDATE, const.ODL_CREATE)),
        ("port_create_depends_on_older_subnet_delete",
         port_fail_subnet_dep(const.ODL_DELETE, const.ODL_CREATE)),
        ("port_create_doesnt_depend_on_newer_subnet_create",
         port_succeed_subnet_dep(const.ODL_CREATE, const.ODL_CREATE)),
        ("port_create_doesnt_depend_on_newer_subnet_update",
         port_succeed_subnet_dep(const.ODL_UPDATE, const.ODL_CREATE)),
        ("port_create_doesnt_depend_on_newer_subnet_delete",
         port_succeed_subnet_dep(const.ODL_DELETE, const.ODL_CREATE)),
        ("port_update_depends_on_older_subnet_create",
         port_fail_subnet_dep(const.ODL_CREATE, const.ODL_UPDATE)),
        ("port_update_depends_on_older_subnet_update",
         port_fail_subnet_dep(const.ODL_UPDATE, const.ODL_UPDATE)),
        ("port_update_depends_on_older_subnet_delete",
         port_fail_subnet_dep(const.ODL_DELETE, const.ODL_UPDATE)),
        ("port_update_doesnt_depend_on_newer_subnet_create",
         port_succeed_subnet_dep(const.ODL_CREATE, const.ODL_UPDATE)),
        ("port_update_doesnt_depend_on_newer_subnet_update",
         port_succeed_subnet_dep(const.ODL_UPDATE, const.ODL_UPDATE)),
        ("port_update_doesnt_depend_on_newer_subnet_delete",
         port_succeed_subnet_dep(const.ODL_DELETE, const.ODL_UPDATE)),
    )


def trunk_dep(first_type, second_type, first_op, second_op, result,
              sub_port=False):
    expected = {'fail': 1, 'pass': 0}
    port_id = _SUBPORT_ID if sub_port else _PORT_ID
    type_id = {const.ODL_PORT: port_id,
               const.ODL_TRUNK: _TRUNK_ID}
    return {'expected': expected[result],
            'first_type': first_type,
            'first_operation': first_op,
            'first_id': type_id[first_type],
            'second_type': second_type,
            'second_operation': second_op,
            'second_id': type_id[second_type]}


class TrunkDependencyValidationsTestCase(
        test_base_db.ODLBaseDbTestCase, BaseDependencyValidationsTestCase):
    scenarios = (
        ("trunk_create_depends_on_older_port_create",
         trunk_dep(const.ODL_PORT, const.ODL_TRUNK,
                   const.ODL_CREATE, const.ODL_CREATE, 'fail')),
        ("trunk_create_doesnt_depend_on_newer_port_create",
         trunk_dep(const.ODL_TRUNK, const.ODL_PORT,
                   const.ODL_CREATE, const.ODL_CREATE, 'pass')),
        ("trunk_create_doesnt_depend_on_port_update",
         trunk_dep(const.ODL_TRUNK, const.ODL_PORT,
                   const.ODL_CREATE, const.ODL_UPDATE, 'pass')),
        ("trunk_create_doesnt_depend_on_newer_port_delete",
         trunk_dep(const.ODL_TRUNK, const.ODL_PORT,
                   const.ODL_CREATE, const.ODL_DELETE, 'pass')),
        # TODO(vthapar): add more/better validations for subport
        # trunk update means subport add/delete
        ("trunk_update_depends_on_older_trunk_create",
         trunk_dep(const.ODL_TRUNK, const.ODL_TRUNK,
                   const.ODL_CREATE, const.ODL_UPDATE, 'fail', True)),
        ("trunk_update_depends_on_older_port_create",
         trunk_dep(const.ODL_PORT, const.ODL_TRUNK,
                   const.ODL_CREATE, const.ODL_UPDATE, 'fail', True)),
        ("trunk_update_doesnt_depend_on_newer_port_create",
         trunk_dep(const.ODL_TRUNK, const.ODL_PORT,
                   const.ODL_UPDATE, const.ODL_CREATE, 'pass', True)),
        ("trunk_update_doesnt_depend_on_port_update",
         trunk_dep(const.ODL_TRUNK, const.ODL_PORT,
                   const.ODL_UPDATE, const.ODL_UPDATE, 'pass', True)),
        ("trunk_update_doesnt_depend_on_newer_port_delete",
         trunk_dep(const.ODL_TRUNK, const.ODL_PORT,
                   const.ODL_UPDATE, const.ODL_DELETE, 'pass', True)),
        # trunk delete cases
        ("trunk_delete_depends_on_older_trunk_create",
         trunk_dep(const.ODL_TRUNK, const.ODL_TRUNK,
                   const.ODL_CREATE, const.ODL_DELETE, 'fail', True)),
        ("trunk_delete_depends_on_older_trunk_update",
         trunk_dep(const.ODL_TRUNK, const.ODL_TRUNK,
                   const.ODL_UPDATE, const.ODL_DELETE, 'fail', True)),
        ("trunk_delete_doesnt_depend_on_older_port_create",
         trunk_dep(const.ODL_PORT, const.ODL_TRUNK,
                   const.ODL_CREATE, const.ODL_DELETE, 'pass')),
    )


def l2gw_dep(first_type, second_type, first_op, second_op, result):
    expected = {'fail': 1, 'pass': 0}
    type_id = {const.ODL_NETWORK: _NET_ID,
               const.ODL_L2GATEWAY: _L2GW_ID,
               const.ODL_L2GATEWAY_CONNECTION: _L2GWCONN_ID}
    return {'expected': expected[result],
            'first_type': first_type,
            'first_operation': first_op,
            'first_id': type_id[first_type],
            'second_type': second_type,
            'second_operation': second_op,
            'second_id': type_id[second_type]}


class L2GWDependencyValidationsTestCase(
        test_base_db.ODLBaseDbTestCase, BaseDependencyValidationsTestCase):
    scenarios = (
        ("L2GWConn_create_depends_on_older_network_create",
         l2gw_dep(const.ODL_NETWORK, const.ODL_L2GATEWAY_CONNECTION,
                  const.ODL_CREATE, const.ODL_CREATE, 'fail')),
        ("L2GWConn_create_depends_on_older_L2GW_create",
         l2gw_dep(const.ODL_L2GATEWAY, const.ODL_L2GATEWAY_CONNECTION,
                  const.ODL_CREATE, const.ODL_CREATE, 'fail')),
        ("L2GWConn_create_doesnt_depend_on_newer_network_create",
         l2gw_dep(const.ODL_L2GATEWAY_CONNECTION, const.ODL_NETWORK,
                  const.ODL_CREATE, const.ODL_CREATE, 'pass')),
        ("L2GWConn_create_doesnt_depend_on_newer_L2GW_create",
         l2gw_dep(const.ODL_L2GATEWAY_CONNECTION, const.ODL_L2GATEWAY,
                  const.ODL_CREATE, const.ODL_CREATE, 'pass')),
    )


# TODO(vthapar): Refactor *_dep into a common method
def bgpvpn_dep(first_type, second_type, first_op, second_op, result):
    expected = {'fail': 1, 'pass': 0}
    type_id = {const.ODL_NETWORK: _NET_ID,
               const.ODL_ROUTER: _ROUTER_ID,
               const.ODL_BGPVPN: _BGPVPN_ID}
    return {'expected': expected[result],
            'first_type': first_type,
            'first_operation': first_op,
            'first_id': type_id[first_type],
            'second_type': second_type,
            'second_operation': second_op,
            'second_id': type_id[second_type]}


class BGPVPNDependencyValidationsTestCase(
        test_base_db.ODLBaseDbTestCase, BaseDependencyValidationsTestCase):
    scenarios = (
        ("bgpvpn_create_doesnt_depend_on_older_network_create",
         bgpvpn_dep(const.ODL_NETWORK, const.ODL_BGPVPN,
                    const.ODL_CREATE, const.ODL_CREATE, 'pass')),
        ("bgpvpn_create_doesnt_depend_on_newer_network_create",
         bgpvpn_dep(const.ODL_BGPVPN, const.ODL_NETWORK,
                    const.ODL_CREATE, const.ODL_CREATE, 'pass')),
        ("bgpvpn_create_doesnt_depend_on_older_router_create",
         bgpvpn_dep(const.ODL_ROUTER, const.ODL_BGPVPN,
                    const.ODL_CREATE, const.ODL_CREATE, 'pass')),
        ("bgpvpn_create_doesnt_depend_on_newer_router_create",
         bgpvpn_dep(const.ODL_BGPVPN, const.ODL_ROUTER,
                    const.ODL_CREATE, const.ODL_CREATE, 'pass')),
        ("bgpvpn_update_depends_on_older_bgpvpn_create",
         bgpvpn_dep(const.ODL_BGPVPN, const.ODL_BGPVPN,
                    const.ODL_CREATE, const.ODL_UPDATE, 'fail')),
        ("bgpvpn_update_depends_on_older_network_create",
         bgpvpn_dep(const.ODL_NETWORK, const.ODL_BGPVPN,
                    const.ODL_CREATE, const.ODL_UPDATE, 'fail')),
        ("bgpvpn_update_doesnt_depend_on_newer_network_create",
         bgpvpn_dep(const.ODL_BGPVPN, const.ODL_NETWORK,
                    const.ODL_UPDATE, const.ODL_CREATE, 'pass')),
        ("bgpvpn_update_depends_on_older_router_create",
         bgpvpn_dep(const.ODL_ROUTER, const.ODL_BGPVPN,
                    const.ODL_CREATE, const.ODL_UPDATE, 'fail')),
        ("bgpvpn_update_doesnt_depend_on_newer_router_create",
         bgpvpn_dep(const.ODL_BGPVPN, const.ODL_ROUTER,
                    const.ODL_UPDATE, const.ODL_CREATE, 'pass')),
        # bgpvpn delete cases
        ("bgpvpn_delete_depends_on_older_bgpvpn_create",
         bgpvpn_dep(const.ODL_BGPVPN, const.ODL_BGPVPN,
                    const.ODL_CREATE, const.ODL_DELETE, 'fail')),
        ("bgpvpn_delete_depends_on_older_bgpvpn_update",
         bgpvpn_dep(const.ODL_BGPVPN, const.ODL_BGPVPN,
                    const.ODL_UPDATE, const.ODL_DELETE, 'fail')),
        ("bgpvpn_delete_doesnt_depend_on_older_network_create",
         bgpvpn_dep(const.ODL_NETWORK, const.ODL_BGPVPN,
                    const.ODL_CREATE, const.ODL_DELETE, 'pass')),
        ("bgpvpn_delete_doesnt_depend_on_older_router_create",
         bgpvpn_dep(const.ODL_ROUTER, const.ODL_BGPVPN,
                    const.ODL_CREATE, const.ODL_DELETE, 'pass')),
    )
