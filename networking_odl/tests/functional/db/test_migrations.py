# Copyright 2016 Intel Corporation.
# Copyright 2016 Isaku Yamahata <isaku.yamahata at intel com>
#                               <isaku.yamahata at gmail com>
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

from oslo_config import cfg
from sqlalchemy import sql
from sqlalchemy.sql import schema

from neutron.db.migration.alembic_migrations import external
from neutron.db.migration import cli as migration
from neutron.tests.functional.db import test_migrations
from neutron.tests.unit import testlib_api

from networking_odl.db import head

FWAAS_TABLES = [
    'cisco_firewall_associations',
    'firewall_group_port_associations_v2',
    'firewall_groups_v2',
    'firewall_policies_v2',
    'firewall_policy_rule_associations_v2',
    'firewall_router_associations',
    'firewall_rules_v2',
]

L2GW_TABLES = [
    'l2gatewayconnections',
    'l2gatewaydevices',
    'l2gatewayinterfaces',
    'l2gateways',
    'l2gw_alembic_version',
    'logical_switches',
    'pending_ucast_macs_remotes',
    'physical_locators',
    'physical_ports',
    'physical_switches',
    'ucast_macs_locals',
    'ucast_macs_remotes',
    'vlan_bindings',
]

BGPVPN_TABLES = [
    'bgpvpns',
    'bgpvpn_network_associations',
    'bgpvpn_router_associations',
]

# EXTERNAL_TABLES should contain all names of tables that are not related to
# current repo.
EXTERNAL_TABLES = set(external.TABLES + FWAAS_TABLES +
                      L2GW_TABLES + BGPVPN_TABLES)

VERSION_TABLE = 'odl_alembic_version'


class _TestModelsMigrationsODL(test_migrations._TestModelsMigrations):
    def db_sync(self, engine):
        self.cfg.config(connection=engine.url, group='database')
        for conf in migration.get_alembic_configs():
            self.alembic_config = conf
            self.alembic_config.neutron_config = cfg.CONF
            migration.do_alembic_command(conf, 'upgrade', 'heads')

    def get_metadata(self):
        return head.get_metadata()

    def include_object(self, object_, name, type_, reflected, compare_to):
        if type_ == 'table' and (name.startswith('alembic') or
                                 name == VERSION_TABLE or
                                 name in EXTERNAL_TABLES):
            return False
        if type_ == 'index' and reflected and name.startswith("idx_autoinc_"):
            return False
        return True

    def _filter_mysql_server_func_now(self, diff_elem):
        # TODO(yamahata): remove this bug work around once it's fixed
        # example:
        # when the column has server_default=sa.func.now(), the diff
        # includes the followings diff
        # [ ('modify_default',
        #     None,
        #    'opendaylightjournal',
        #    'created_at',
        #   {'existing_nullable': True,
        #    'existing_type': DATETIME()},
        # DefaultClause(<sqlalchemy.sql.elements.TextClause object
        #               at 0x7f652188ce50>, for_update=False),
        # DefaultClause(<sqlalchemy.sql.functions.now at 0x7f6522411050; now>,
        #               for_update=False))]
        # another example
        # [ ('modify_default',
        #     None,
        #    'opendaylightjournal',
        #    'created_at',
        #   {'existing_nullable': True,
        #    'existing_type': DATETIME()},
        #     None,
        #   DefaultClause(<sqlalchemy.sql.functions.now at 0x7ff3b3517410;
        #                  now>,
        #                 for_update=False))]

        meta_def = diff_elem[0][5]
        rendered_meta_def = diff_elem[0][6]
        if (diff_elem[0][0] == 'modify_default' and
                diff_elem[0][2] in ('opendaylightjournal',
                                    'opendaylight_periodic_task') and
                isinstance(meta_def, schema.DefaultClause) and
                isinstance(meta_def.arg, sql.elements.TextClause) and
                meta_def.reflected and
                meta_def.arg.text == u'CURRENT_TIMESTAMP' and
                isinstance(rendered_meta_def, schema.DefaultClause) and
                isinstance(rendered_meta_def.arg, sql.functions.now) and
                not rendered_meta_def.reflected and
                meta_def.for_update == rendered_meta_def.for_update):
            return False

        return True

    def filter_metadata_diff(self, diff):
        return filter(self._filter_mysql_server_func_now, diff)


class TestModelsMigrationsMysql(testlib_api.MySQLTestCaseMixin,
                                _TestModelsMigrationsODL,
                                testlib_api.SqlTestCaseLight):
    pass


class TestModelsMigrationsPostgresql(testlib_api.PostgreSQLTestCaseMixin,
                                     _TestModelsMigrationsODL,
                                     testlib_api.SqlTestCaseLight):
    pass
