#
# Copyright (C) 2016 Red Hat, Inc.
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

import mock
import requests

from networking_l2gw.services.l2gateway.common import constants as l2gw_const
from networking_sfc.extensions import flowclassifier as fc_const
from networking_sfc.extensions import sfc as sfc_const
from neutron.services.trunk import constants as t_consts
from neutron_lib.api.definitions import bgpvpn as bgpvpn_const
from neutron_lib.plugins import constants
from neutron_lib.plugins import directory

from networking_odl.bgpvpn import odl_v2 as bgpvpn_driver
from networking_odl.common import constants as odl_const
from networking_odl.common import exceptions
from networking_odl.db import db
from networking_odl.journal import base_driver
from networking_odl.journal import full_sync
from networking_odl.journal import journal
from networking_odl.l2gateway import driver_v2 as l2gw_driver
from networking_odl.l3 import l3_odl_v2
from networking_odl.lbaas import lbaasv2_driver_v2 as lbaas_driver
from networking_odl.ml2 import mech_driver_v2
from networking_odl.qos import qos_driver_v2 as qos_driver
from networking_odl.sfc.flowclassifier import sfc_flowclassifier_v2
from networking_odl.sfc import sfc_driver_v2 as sfc_driver
from networking_odl.tests import base
from networking_odl.tests.unit.journal import helper
from networking_odl.tests.unit import test_base_db
from networking_odl.trunk import trunk_driver_v2 as trunk_driver


class FullSyncTestCase(test_base_db.ODLBaseDbTestCase):
    def setUp(self):
        self.useFixture(
            base.OpenDaylightRestClientGlobalFixture(full_sync._CLIENT))
        super(FullSyncTestCase, self).setUp()

        self._CLIENT = full_sync._CLIENT.get_client()
        self.addCleanup(full_sync.FULL_SYNC_RESOURCES.clear)
        # NOTE(rajivk) workaround, Fixture defined are executed after complete
        # tests cases, but cleanup is needed after each test case.
        self.addCleanup(self._clean_registered_plugins)

    def _clean_registered_plugins(self):
        for plugin_type in self._get_all_plugins().keys():
            directory.add_plugin(plugin_type, None)

    def test_no_full_sync_when_canary_exists(self):
        full_sync.full_sync(self.db_context)
        self.assertEqual([], db.get_all_db_rows(self.db_context))

    def _filter_out_canary(self, rows):
        return [row for row in rows if row['object_uuid'] !=
                full_sync._CANARY_NETWORK_ID]

    def _mock_l2_resources(self):
        expected_journal = {odl_const.ODL_NETWORK: '1',
                            odl_const.ODL_SUBNET: '2',
                            odl_const.ODL_PORT: '3'}
        network_id = expected_journal[odl_const.ODL_NETWORK]
        plugin = mock.Mock()
        plugin.get_networks.return_value = [{'id': network_id}]
        plugin.get_subnets.return_value = [
            {'id': expected_journal[odl_const.ODL_SUBNET],
             'network_id': network_id}]
        port = {'id': expected_journal[odl_const.ODL_PORT],
                odl_const.ODL_SGS: None,
                'tenant_id': '123',
                'fixed_ips': [],
                'network_id': network_id}
        plugin.get_ports.side_effect = ([port], [])
        directory.add_plugin(constants.CORE, plugin)
        return expected_journal

    def _test_no_full_sync_when_canary_in_journal(self, state):
        self._mock_canary_missing()
        self._mock_l2_resources()
        db.create_pending_row(self.db_context, odl_const.ODL_NETWORK,
                              full_sync._CANARY_NETWORK_ID,
                              odl_const.ODL_CREATE, {})
        row = db.get_all_db_rows(self.db_context)[0]
        db.update_db_row_state(self.db_context, row, state)

        full_sync.full_sync(self.db_context)

        rows = db.get_all_db_rows(self.db_context)
        self.assertEqual([], self._filter_out_canary(rows))

    def test_no_full_sync_when_canary_pending_creation(self):
        self._test_no_full_sync_when_canary_in_journal(odl_const.PENDING)

    def test_no_full_sync_when_canary_is_processing(self):
        self._test_no_full_sync_when_canary_in_journal(odl_const.PROCESSING)

    @staticmethod
    def _get_all_resources():
        return (
            (odl_const.ODL_SG, constants.CORE),
            (odl_const.ODL_SG_RULE, constants.CORE),
            (odl_const.ODL_NETWORK, constants.CORE),
            (odl_const.ODL_SUBNET, constants.CORE),
            (odl_const.ODL_ROUTER, constants.L3),
            (odl_const.ODL_PORT, constants.CORE),
            (odl_const.ODL_FLOATINGIP, constants.L3),
            (odl_const.ODL_LOADBALANCER, constants.LOADBALANCERV2),
            (odl_const.ODL_LISTENER, constants.LOADBALANCERV2),
            (odl_const.ODL_POOL, constants.LOADBALANCERV2),
            (odl_const.ODL_MEMBER, constants.LOADBALANCERV2),
            (odl_const.ODL_HEALTHMONITOR, constants.LOADBALANCERV2),
            (odl_const.ODL_QOS_POLICY, constants.QOS),
            (odl_const.ODL_TRUNK, t_consts.TRUNK),
            (odl_const.ODL_BGPVPN, bgpvpn_const.ALIAS),
            (odl_const.ODL_BGPVPN_NETWORK_ASSOCIATION, bgpvpn_const.ALIAS),
            (odl_const.ODL_BGPVPN_ROUTER_ASSOCIATION, bgpvpn_const.ALIAS),
            (odl_const.ODL_SFC_FLOW_CLASSIFIER, fc_const.FLOW_CLASSIFIER_EXT),
            (odl_const.ODL_SFC_PORT_PAIR, sfc_const.SFC_EXT),
            (odl_const.ODL_SFC_PORT_PAIR_GROUP, sfc_const.SFC_EXT),
            (odl_const.ODL_SFC_PORT_CHAIN, sfc_const.SFC_EXT),
            (odl_const.ODL_L2GATEWAY, l2gw_const.L2GW),
            (odl_const.ODL_L2GATEWAY_CONNECTION, l2gw_const.L2GW))

    @mock.patch.object(db, 'delete_pending_rows')
    @mock.patch.object(full_sync, '_full_sync_needed')
    @mock.patch.object(full_sync, '_sync_resources')
    @mock.patch.object(journal, 'record')
    def test_sync_resource_order(
            self, record_mock, _sync_resources_mock, _full_sync_needed_mock,
            delete_pending_rows_mock):
        all_resources = self._get_all_resources()
        full_sync.FULL_SYNC_RESOURCES = {resource_type: mock.Mock()
                                         for resource_type, _ in all_resources}
        _full_sync_needed_mock._full_sync_needed.return_value = True
        context = mock.MagicMock()
        full_sync.full_sync(context)

        _sync_resources_mock.assert_has_calls(
            [mock.call(mock.ANY, object_type, mock.ANY)
                for object_type, _ in all_resources])

    def test_client_error_propagates(self):
        class TestException(Exception):
            def __init__(self):
                pass

        self._CLIENT.get.side_effect = TestException()
        self.assertRaises(TestException, full_sync.full_sync, self.db_context)

    def _mock_canary_missing(self):
        get_return = mock.MagicMock()
        get_return.status_code = requests.codes.not_found
        self._CLIENT.get.return_value = get_return

    def _assert_canary_created(self):
        rows = db.get_all_db_rows(self.db_context)
        self.assertTrue(any(r['object_uuid'] == full_sync._CANARY_NETWORK_ID
                            for r in rows))
        return rows

    def _test_full_sync_resources(self, expected_journal):
        self._mock_canary_missing()
        directory.add_plugin(constants.CORE, mock.Mock())
        full_sync.full_sync(self.db_context)

        rows = self._assert_canary_created()
        rows = self._filter_out_canary(rows)
        self.assertItemsEqual(expected_journal.keys(),
                              [row['object_type'] for row in rows])
        for row in rows:
            self.assertEqual(expected_journal[row['object_type']],
                             row['object_uuid'])

    def test_full_sync_removes_pending_rows(self):
        db.create_pending_row(self.db_context, odl_const.ODL_NETWORK, "uuid",
                              odl_const.ODL_CREATE, {'foo': 'bar'})
        self._test_full_sync_resources({})

    def test_full_sync_no_resources(self):
        self._test_full_sync_resources({})

    @staticmethod
    def _get_mocked_security_groups(context):
        return [{'description': u'description',
                 'security_group_rules': ['security_grp_rules'],
                 'id': 'test_uuid', 'name': u'default'}]

    @staticmethod
    def _get_mocked_security_group_rules(context):
        return [{'direction': 'egress', 'protocol': None,
                 'description': 'description', 'port_range_max': None,
                 'id': 'test_uuid', 'security_group_id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_networks(context):
        return [{'id': 'test_uuid', 'project_id': u'project_id',
                 'status': u'ACTIVE', 'subnets': [], 'description': u'',
                 'name': u'network0'}]

    @staticmethod
    def _get_mocked_subnets(context):
        return [{'description': u'', 'cidr': u'test-cidr', 'id': 'test_uuid',
                 'name': u'test-subnet', 'network_id': 'test_uuid',
                 'gateway_ip': u'gateway_ip'}]

    @staticmethod
    def _get_mocked_routers(context):
        return [{'status': u'ACTIVE', 'description': u'', 'name': u'router1',
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_ports(context):
        return [{'status': u'DOWN', 'description': None, 'id': 'test_uuid',
                 'name': u'loadbalancer-27', 'network_id': 'test_uuid',
                 'mac_address': u'fa:16:3e:69:4e:33'}]

    @staticmethod
    def _get_mocked_loadbalancers(context):
        return [{'description': '', 'tenant_id': 'tenant_id',
                 'vip_subnet_id': 'subnet_id', 'listeners': [],
                 'vip_address': '10.1.0.11', 'vip_port_id': 'port_id',
                 'pools': [], 'id': 'test_uuid', 'name': 'test-lb'}]

    @staticmethod
    def _get_mocked_listeners(context):
        return [{'admin_state_up': True, 'project_id': 'test_uuid',
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_trunks(context):
        return [{'routers': [], 'id': 'test_uuid', 'name': u'',
                 'tenant_id': u'project_id', 'networks': [], 'route_targets': [
                     u'64512:1'], 'project_id': u'project_id', 'type': 'l3'},
                {'routers': [], 'id': 'test_uuid', 'name': u'',
                 'tenant_id': u'tenant_id', 'networks': [], 'route_targets': [
                 u'64512:1'], 'project_id': u'project_id', 'type': 'l3'}]

    @staticmethod
    def _get_mocked_bgpvpns(context):
        return [{'network_id': 'test_uuid', 'bgpvpn_id': 'test_uuid',
                 'project_id': 'test_uuid', 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_l2_gateways(context):
        return [{'tenant_id': u'test_tenant_id', 'id': 'test_uuid',
                 'devices': [{'interfaces': [{'name': u'eth3'}],
                              'id': 'test_uuid', 'device_name': u'vtep0'}],
                 'name': u'test-gateway'}]

    @staticmethod
    def _get_mocked_l2_gateway_connections(context):
        return [{'network_id': 'test_uuid', 'tenant_id': 'test_uuid',
                 'l2_gateway_id': 'test_uuid', 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_pools(context):
        return [{'name': 'pool1', 'admin_state_up': True,
                 'project_id': 'test_uuid', 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_pool_members(context, pool_id):
        return [{'name': 'pool1', 'admin_state_up': True,
                 'project_id': 'test_uuid', 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_healthmonitors(context):
        return [{'type': 'HTTP', 'admin_state_up': True,
                 'project_id': 'test_uuid', 'id': 'test_uuid',
                 'name': 'monitor1'}]

    @staticmethod
    def _get_mocked_listener(context):
        return [{'admin_state_up': True, 'project_id': 'test_uuid',
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_floatingips(context):
        return [{'floating_network_id': 'test_uuid', 'tenant_id': 'test_uuid',
                 'dns_name': '', 'dns_domain': '', 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_policies(context):
        return [{'id': 'test_uuid', 'project_id': 'test_uuid',
                 'name': 'test-policy', 'description': 'Policy description',
                 'shared': True, 'is_default': False}]

    @staticmethod
    def _get_mocked_bgpvpn_network_associations(context, bgpvpn_id):
        return [{'network_id': 'test_uuid', 'tenant_id': 'test_uuid',
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_bgpvpn_router_associations(context, bgpvpn_id):
        return [{'router_id': 'test_uuid', 'tenant_id': 'test_uuid',
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_port_chains(context):
        tenant_id = 'test_uuid'
        return [{'tenant_id': tenant_id, 'project_id': tenant_id,
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_port_pair_groups(context):
        tenant_id = 'test_uuid'
        return [{'tenant_id': tenant_id, 'project_id': tenant_id,
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_port_pairs(context):
        tenant_id = 'test_uuid'
        return [{'tenant_id': tenant_id, 'project_id': tenant_id,
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_mocked_flowclassifiers(context):
        tenant_id = 'test_uuid'
        return [{'tenant_id': tenant_id, 'project_id': tenant_id,
                 'id': 'test_uuid'}]

    @staticmethod
    def _get_all_plugins():
        return {
            constants.CORE: (mock.Mock(),
                             mech_driver_v2.OpenDaylightMechanismDriver),
            constants.L3: (mock.Mock(), l3_odl_v2.OpenDaylightL3RouterPlugin),
            constants.LOADBALANCERV2: (mock.Mock(),
                                       lbaas_driver.OpenDaylightManager),
            t_consts.TRUNK: (mock.Mock(),
                             trunk_driver.OpenDaylightTrunkHandlerV2),
            constants.QOS: (mock.Mock(), qos_driver.OpenDaylightQosDriver),
            sfc_const.SFC_EXT: (mock.Mock(),
                                sfc_driver.OpenDaylightSFCDriverV2),
            bgpvpn_const.ALIAS: (mock.Mock(),
                                 bgpvpn_driver.OpenDaylightBgpvpnDriver),
            fc_const.FLOW_CLASSIFIER_EXT: (
                mock.Mock(),
                sfc_flowclassifier_v2.OpenDaylightSFCFlowClassifierDriverV2),
            l2gw_const.L2GW: (mock.Mock(), l2gw_driver.OpenDaylightL2gwDriver)
        }

    @staticmethod
    def _get_name(resource_type):
        MEMBERS = 'pool_members'
        mapping = {
            odl_const.ODL_QOS_POLICY: odl_const.ODL_QOS_POLICIES,
            odl_const.ODL_MEMBER: MEMBERS,
            odl_const.ODL_SFC_PORT_PAIR:
                odl_const.NETWORKING_SFC_FLOW_CLASSIFIERS,
            odl_const.ODL_SFC_PORT_PAIR:
                odl_const.NETWORKING_SFC_PORT_PAIRS,
            odl_const.ODL_SFC_PORT_PAIR_GROUP:
                odl_const.NETWORKING_SFC_PORT_PAIR_GROUPS,
            odl_const.ODL_SFC_PORT_CHAIN: odl_const.NETWORKING_SFC_PORT_CHAINS,
            odl_const.ODL_L2GATEWAY_CONNECTION:
                odl_const.ODL_L2GATEWAY_CONNECTIONS}

        return ('_get_mocked_%s' % mapping.get(
            resource_type, resource_type + 's'))

    def _add_side_effect(self):
        plugins = self._get_all_plugins()
        resources = self._get_all_resources()
        for resource_type, plugin_name in resources:
            name = self._get_name(resource_type)
            setattr(plugins[plugin_name][0], "get_%s" % name[12:],
                    getattr(self, name))

            if directory.get_plugin(plugin_name) is None:
                directory.add_plugin(plugin_name, plugins[plugin_name][0])

    @mock.patch.object(journal, 'record')
    def _test_sync_resources(self, object_type, plugin_type, mocked_record):
        plugins = self._get_all_plugins()
        driver = plugins[plugin_type][1]
        args = [mock.Mock()]
        if object_type in [odl_const.ODL_MEMBER,
                           odl_const.ODL_BGPVPN_ROUTER_ASSOCIATION,
                           odl_const.ODL_BGPVPN_NETWORK_ASSOCIATION]:
            args.append(mock.Mock())

        resources = getattr(self, self._get_name(object_type))(*args)
        context = mock.Mock()

        def _test_get_default_handler(context, resource_type,
                                      plugin_type=plugin_type):

            resource_type = self._get_name(resource_type)[12:]
            return full_sync.get_resources(context, plugin_type=plugin_type,
                                           resource_type=resource_type)

        handler = getattr(driver, 'get_resources', _test_get_default_handler)
        full_sync._sync_resources(context, object_type, handler)
        mocked_record.assert_has_calls(
            [mock.call(context, object_type, resource['id'],
                       odl_const.ODL_CREATE,
                       resource) for resource in resources])

    def test_sync_all_resources(self):
        self._add_side_effect()
        resources = self._get_all_resources()
        for obj_type, plugin_name in resources:
            self._test_sync_resources(obj_type, plugin_name)

    def test_full_sync_retries_exceptions(self):
        with mock.patch.object(full_sync, '_full_sync_needed') as m:
            self._test_retry_exceptions(full_sync.full_sync, m)

    def test_object_not_registered(self):
        self.assertRaises(exceptions.ResourceNotRegistered,
                          full_sync.sync_resources,
                          self.db_context,
                          'test-object-type')
        self.assertEqual([], db.get_all_db_rows(self.db_context))

    def _register_resources(self):
        helper.TestDriver()
        self.addCleanup(base_driver.ALL_RESOURCES.clear)

    def add_plugin(self, plugin_type, plugin):
        directory.add_plugin(plugin_type, plugin)

    def test_plugin_not_registered(self):
        self._register_resources()
        # NOTE(rajivk): workaround, as we don't have delete method for plugin
        plugin = directory.get_plugin(helper.TEST_PLUGIN)
        directory.add_plugin(helper.TEST_PLUGIN, None)
        self.addCleanup(self.add_plugin, helper.TEST_PLUGIN, plugin)
        self.assertRaises(exceptions.PluginMethodNotFound,
                          full_sync.sync_resources,
                          self.db_context,
                          helper.TEST_RESOURCE1)
        self.assertEqual([], db.get_all_db_rows(self.db_context))

    def test_sync_resources(self):
        self._register_resources()
        plugin = helper.TestPlugin()
        self.add_plugin(helper.TEST_PLUGIN, plugin)
        resources = plugin.get_test_resource1s(self.db_context)
        full_sync.sync_resources(self.db_context,
                                 helper.TEST_RESOURCE1)
        entries = [entry.data for entry in db.get_all_db_rows(self.db_context)]
        for resource in resources:
            self.assertIn(resource, entries)
        self.assertEqual(len(resources), len(entries))

    @mock.patch.object(base_driver.ResourceBaseDriver,
                       'get_resources_for_full_sync')
    def test_get_resources_failed(self, mock_get_resources):
        self._register_resources()
        mock_get_resources.side_effect = exceptions.UnsupportedResourceType()
        resource_name = helper.TEST_RESOURCE1
        self.assertRaises(exceptions.UnsupportedResourceType,
                          full_sync.sync_resources, self.db_context,
                          resource_name)

        mock_get_resources.assert_called_once_with(self.db_context,
                                                   resource_name)

        self.assertEqual([], db.get_all_db_rows(self.db_context))
