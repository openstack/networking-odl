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


def subnet_data(operation):
    if operation == const.ODL_DELETE:
        return 'NET_ID'

    return {'network_id': 'NET_ID'}


def subnet_fail_network_dep(net_op, subnet_op):
    return {'expected': (None, False),
            'first_type': const.ODL_NETWORK,
            'first_operation': net_op,
            'first_id': 'NET_ID',
            'first_data': None,
            'second_type': const.ODL_SUBNET,
            'second_operation': subnet_op,
            'second_id': 'SUBNET_ID',
            'second_data': subnet_data(subnet_op)}


def subnet_succeed_network_dep(net_op, subnet_op):
    return {'expected': (True, None),
            'first_type': const.ODL_SUBNET,
            'first_operation': subnet_op,
            'first_id': 'SUBNET_ID',
            'first_data': subnet_data(subnet_op),
            'second_type': const.ODL_NETWORK,
            'second_operation': net_op,
            'second_id': 'NET_ID',
            'second_data': None}


class BaseDependencyValidationsTestCase(object):
    def test_dependency(self):
        db.create_pending_row(
            self.db_session, self.first_type, self.first_id,
            self.first_operation, self.first_data)
        db.create_pending_row(
            self.db_session, self.second_type, self.second_id,
            self.second_operation, self.second_data)

        for idx, row in enumerate(db.get_all_db_rows(self.db_session)):
            if self.expected[idx] is not None:
                self.assertEqual(
                    self.expected[idx],
                    dependency_validations.validate(self.db_session, row))


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
        ("subnet_delete_doesnt_depend_on_older_network_delete",
         subnet_succeed_network_dep(const.ODL_DELETE, const.ODL_DELETE)),
        ("subnet_delete_doesnt_depend_on_newer_network_create",
         subnet_succeed_network_dep(const.ODL_CREATE, const.ODL_DELETE)),
        ("subnet_delete_doesnt_depend_on_newer_network_update",
         subnet_succeed_network_dep(const.ODL_UPDATE, const.ODL_DELETE)),
        ("subnet_delete_doesnt_depend_on_newer_network_delete",
         subnet_succeed_network_dep(const.ODL_DELETE, const.ODL_DELETE)),
    )


port_data = {'network_id': 'NET_ID',
             'fixed_ips': [{'subnet_id': 'SUBNET_ID'}]}


def port_fail_network_dep(net_op, port_op):
    return {'expected': (None, False),
            'first_type': const.ODL_NETWORK,
            'first_operation': net_op,
            'first_id': 'NET_ID',
            'first_data': None,
            'second_type': const.ODL_PORT,
            'second_operation': port_op,
            'second_id': 'PORT_ID',
            'second_data': port_data}


def port_succeed_network_dep(net_op, port_op):
    return {'expected': (True, None),
            'first_type': const.ODL_PORT,
            'first_operation': port_op,
            'first_id': 'PORT_ID',
            'first_data': port_data,
            'second_type': const.ODL_NETWORK,
            'second_operation': net_op,
            'second_id': 'NET_ID',
            'second_data': None}


def port_fail_subnet_dep(net_op, port_op):
    return {'expected': (None, False),
            'first_type': const.ODL_SUBNET,
            'first_operation': net_op,
            'first_id': 'SUBNET_ID',
            'first_data': None,
            'second_type': const.ODL_PORT,
            'second_operation': port_op,
            'second_id': 'PORT_ID',
            'second_data': port_data}


def port_succeed_subnet_dep(net_op, port_op):
    return {'expected': (True, None),
            'first_type': const.ODL_PORT,
            'first_operation': port_op,
            'first_id': 'PORT_ID',
            'first_data': port_data,
            'second_type': const.ODL_SUBNET,
            'second_operation': net_op,
            'second_id': 'SUBNET_ID',
            'second_data': None}


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
