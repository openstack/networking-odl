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

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.common import filters
from networking_odl.db import db
from networking_odl.journal import journal
from networking_odl.l3 import l3_odl_v2
from networking_odl.ml2 import mech_driver_v2

import mock
from oslo_serialization import jsonutils
import requests

from neutron import context
from neutron.db import api as neutron_db_api
from neutron.extensions import external_net as external_net
from neutron import manager
from neutron.plugins.ml2 import config as config
from neutron.plugins.ml2 import plugin
from neutron.tests import base
from neutron.tests.unit.db import test_db_base_plugin_v2
from neutron.tests.unit import testlib_api

EMPTY_DEP = []
FLOATINGIP_ID = 'floatingip_uuid'
NETWORK_ID = 'network_uuid'
ROUTER_ID = 'router_uuid'
SUBNET_ID = 'subnet_uuid'
PORT_ID = 'port_uuid'


class OpenDayLightMechanismConfigTests(testlib_api.SqlTestCase):

    def _set_config(self, url='http://127.0.0.1:9999', username='someuser',
                    password='somepass'):
        config.cfg.CONF.set_override('mechanism_drivers',
                                     ['logger', 'opendaylight'],
                                     'ml2')
        config.cfg.CONF.set_override('url', url, 'ml2_odl')
        config.cfg.CONF.set_override('username', username, 'ml2_odl')
        config.cfg.CONF.set_override('password', password, 'ml2_odl')

    def _test_missing_config(self, **kwargs):
        self._set_config(**kwargs)
        self.assertRaises(config.cfg.RequiredOptError,
                          plugin.Ml2Plugin)

    def test_valid_config(self):
        self._set_config()
        plugin.Ml2Plugin()

    def test_missing_url_raises_exception(self):
        self._test_missing_config(url=None)

    def test_missing_username_raises_exception(self):
        self._test_missing_config(username=None)

    def test_missing_password_raises_exception(self):
        self._test_missing_config(password=None)


class DataMatcher(object):

    def __init__(self, operation, object_type, object_dict):
        self._data = object_dict.copy()
        self._object_type = object_type
        filter_cls = filters.FILTER_MAP[object_type]
        attr_filter = getattr(filter_cls,
                              'filter_' + operation + '_attributes')
        attr_filter(self._data)

    def __eq__(self, s):
        data = jsonutils.loads(s)
        if self._object_type == odl_const.ODL_ROUTER_INTF:
            return self._data == data
        else:
            return self._data == data[self._object_type]


class OpenDaylightL3TestCase(test_db_base_plugin_v2.NeutronDbPluginV2TestCase,
                             base.BaseTestCase):
    def setUp(self):
        config.cfg.CONF.set_override("core_plugin",
                                     'neutron.plugins.ml2.plugin.Ml2Plugin')
        core_plugin = config.cfg.CONF.core_plugin
        super(OpenDaylightL3TestCase, self).setUp(plugin=core_plugin)
        config.cfg.CONF.set_override('mechanism_drivers',
                                     ['logger', 'opendaylight'], 'ml2')
        config.cfg.CONF.set_override('url', 'http://127.0.0.1:9999', 'ml2_odl')
        config.cfg.CONF.set_override('username', 'someuser', 'ml2_odl')
        config.cfg.CONF.set_override('password', 'somepass', 'ml2_odl')
        mock.patch.object(journal.OpendaylightJournalThread,
                          'start_odl_sync_thread').start()
        self.db_session = neutron_db_api.get_session()
        self.mech = mech_driver_v2.OpenDaylightMechanismDriver()
        self.plugin = manager.NeutronManager.get_plugin()
        self.plugin._network_is_external = mock.Mock(return_value=True)
        self.driver = l3_odl_v2.OpenDaylightL3RouterPlugin()
        self.thread = journal.OpendaylightJournalThread()
        self.driver.get_floatingip = mock.Mock(
            return_value={'router_id': ROUTER_ID,
                          'floating_network_id': NETWORK_ID})
        self.addCleanup(self._db_cleanup)

    @staticmethod
    def _get_mock_router_operation_info(network, subnet):
        router_context = context.get_admin_context()
        router = {odl_const.ODL_ROUTER:
                  {'name': 'router1',
                   'admin_state_up': True,
                   'tenant_id': network['network']['tenant_id'],
                   'external_gateway_info': {'network_id':
                                             network['network']['id']}}}
        return router_context, router

    @staticmethod
    def _get_mock_floatingip_operation_info(network, subnet):
        floatingip_context = context.get_admin_context()
        floatingip = {odl_const.ODL_FLOATINGIP:
                      {'floating_network_id': network['network']['id'],
                       'tenant_id': network['network']['tenant_id']}}
        return floatingip_context, floatingip

    @staticmethod
    def _get_mock_router_interface_operation_info(network, subnet):
        router_intf_context = context.get_admin_context()
        router_intf_dict = {'subnet_id': subnet['subnet']['id'],
                            'id': network['network']['id']}
        return router_intf_context, router_intf_dict

    @classmethod
    def _get_mock_operation_info(cls, object_type, *args):
        getter = getattr(cls, '_get_mock_' + object_type + '_operation_info')
        return getter(*args)

    def _db_cleanup(self):
        rows = db.get_all_db_rows(self.db_session)
        for row in rows:
            db.delete_row(self.db_session, row=row)

    @classmethod
    def _get_mock_request_response(cls, status_code):
        response = mock.Mock(status_code=status_code)
        response.raise_for_status = mock.Mock() if status_code < 400 else (
            mock.Mock(side_effect=requests.exceptions.HTTPError(
                cls._status_code_msgs[status_code])))
        return response

    def _test_operation(self, status_code, expected_calls, *args, **kwargs):
        request_response = self._get_mock_request_response(status_code)
        with mock.patch('requests.request',
                        return_value=request_response) as mock_method:
            with mock.patch.object(self.thread.event, 'wait',
                                   return_value=False):
                self.thread.run_sync_thread(exit_after_run=True)

        if expected_calls:
            mock_method.assert_called_with(
                headers={'Content-Type': 'application/json'},
                auth=(config.cfg.CONF.ml2_odl.username,
                      config.cfg.CONF.ml2_odl.password),
                timeout=config.cfg.CONF.ml2_odl.timeout, *args, **kwargs)
        self.assertEqual(expected_calls, mock_method.call_count)

    def _call_operation_object(self, operation, object_type, object_id,
                               network, subnet):
        object_context, object_dict = self._get_mock_operation_info(
            object_type, network, subnet)
        method = getattr(self.driver, operation + '_' + object_type)

        if operation == odl_const.ODL_CREATE:
            new_object_dict = method(object_context, object_dict)
        elif operation == odl_const.ODL_UPDATE:
            new_object_dict = method(object_context, object_id, object_dict)
        elif operation in [odl_const.ODL_ADD, odl_const.ODL_REMOVE]:
            router_dict = method(object_context, object_id, object_dict)
            new_object_dict = self.driver._generate_router_dict(
                object_id, object_dict, router_dict)
        else:
            new_object_dict = method(object_context, object_id)

        return object_context, new_object_dict

    def _test_operation_thread_processing(self, object_type, operation,
                                          network, subnet, object_id,
                                          expected_calls=1):
        http_requests = {odl_const.ODL_CREATE: 'post',
                         odl_const.ODL_UPDATE: 'put',
                         odl_const.ODL_DELETE: 'delete',
                         odl_const.ODL_ADD: 'put',
                         odl_const.ODL_REMOVE: 'put'}
        status_codes = {odl_const.ODL_CREATE: requests.codes.created,
                        odl_const.ODL_UPDATE: requests.codes.ok,
                        odl_const.ODL_DELETE: requests.codes.no_content,
                        odl_const.ODL_ADD: requests.codes.created,
                        odl_const.ODL_REMOVE: requests.codes.created}

        http_request = http_requests[operation]
        status_code = status_codes[operation]

        # Create database entry.
        object_context, new_object_dict = self._call_operation_object(
            operation, object_type, object_id, network, subnet)

        # Setup expected results.
        if operation in [odl_const.ODL_UPDATE, odl_const.ODL_DELETE]:
            url = (config.cfg.CONF.ml2_odl.url + '/' + object_type + 's/' +
                   object_id)
        elif operation in [odl_const.ODL_ADD, odl_const.ODL_REMOVE]:
            url = (config.cfg.CONF.ml2_odl.url + '/' + odl_const.ODL_ROUTER +
                   's/' + object_id + '/' + operation + '_router_interface')
        else:
            url = config.cfg.CONF.ml2_odl.url + '/' + object_type + 's'

        if operation in [odl_const.ODL_CREATE, odl_const.ODL_UPDATE,
                         odl_const.ODL_ADD, odl_const.ODL_REMOVE]:
            kwargs = {
                'url': url,
                'data': DataMatcher(operation, object_type, new_object_dict)}
        else:
            kwargs = {'url': url, 'data': None}

        # Call threading routine to process database entry. Test results.
        self._test_operation(status_code, expected_calls, http_request,
                             **kwargs)

        return new_object_dict

    def _test_thread_processing(self, object_type):
        # Create network and subnet.
        kwargs = {'arg_list': (external_net.EXTERNAL,),
                  external_net.EXTERNAL: True}
        with self.network(**kwargs) as network:
            with self.subnet(network=network, cidr='10.0.0.0/24'):
                # Add and process create request.
                new_object_dict = self._test_operation_thread_processing(
                    object_type, odl_const.ODL_CREATE, network, None, None)
                object_id = new_object_dict['id']
                rows = db.get_all_db_rows_by_state(self.db_session,
                                                   odl_const.COMPLETED)
                self.assertEqual(1, len(rows))

                # Add and process 'update' request. Adds to database.
                self._test_operation_thread_processing(
                    object_type, odl_const.ODL_UPDATE, network, None,
                    object_id)
                rows = db.get_all_db_rows_by_state(self.db_session,
                                                   odl_const.COMPLETED)
                self.assertEqual(2, len(rows))

                # Add and process 'delete' request. Adds to database.
                self._test_operation_thread_processing(
                    object_type, odl_const.ODL_DELETE, network, None,
                    object_id)
                rows = db.get_all_db_rows_by_state(self.db_session,
                                                   odl_const.COMPLETED)
                self.assertEqual(3, len(rows))

    def _test_db_results(self, object_id, operation, object_type):
        rows = db.get_all_db_rows(self.db_session)

        self.assertEqual(1, len(rows))
        self.assertEqual(operation, rows[0]['operation'])
        self.assertEqual(object_type, rows[0]['object_type'])
        self.assertEqual(object_id, rows[0]['object_uuid'])

        self._db_cleanup()

    def _test_object_db(self, object_type):
        # Create network and subnet for testing.
        kwargs = {'arg_list': (external_net.EXTERNAL,),
                  external_net.EXTERNAL: True}
        with self.network(**kwargs) as network:
            with self.subnet(network=network):
                object_context, object_dict = self._get_mock_operation_info(
                    object_type, network, None)

                # Add and test 'create' database entry.
                method = getattr(self.driver,
                                 odl_const.ODL_CREATE + '_' + object_type)
                new_object_dict = method(object_context, object_dict)
                object_id = new_object_dict['id']
                self._test_db_results(object_id, odl_const.ODL_CREATE,
                                      object_type)

                # Add and test 'update' database entry.
                method = getattr(self.driver,
                                 odl_const.ODL_UPDATE + '_' + object_type)
                method(object_context, object_id, object_dict)
                self._test_db_results(object_id, odl_const.ODL_UPDATE,
                                      object_type)

                # Add and test 'delete' database entry.
                method = getattr(self.driver,
                                 odl_const.ODL_DELETE + '_' + object_type)
                method(object_context, object_id)
                self._test_db_results(object_id, odl_const.ODL_DELETE,
                                      object_type)

    def _test_dependency_processing(
            self, test_operation, test_object, test_id, test_context,
            dep_operation, dep_object, dep_id, dep_context):

        # Mock sendjson to verify that it never gets called.
        mock_sendjson = mock.patch.object(client.OpenDaylightRestClient,
                                          'sendjson').start()

        # Create dependency db row and mark as 'processing' so it won't
        # be processed by the journal thread.
        db.create_pending_row(self.db_session, dep_object,
                              dep_id, dep_operation, dep_context)
        row = db.get_all_db_rows_by_state(self.db_session, odl_const.PENDING)
        db.update_db_row_state(self.db_session, row[0], odl_const.PROCESSING)

        # Create test row with dependent ID.
        db.create_pending_row(self.db_session, test_object,
                              test_id, test_operation, test_context)

        # Call journal thread.
        with mock.patch.object(self.thread.event, 'wait',
                               return_value=False):
            self.thread.run_sync_thread(exit_after_run=True)

        # Verify that dependency row is still set at 'processing'.
        rows = db.get_all_db_rows_by_state(self.db_session,
                                           odl_const.PROCESSING)
        self.assertEqual(1, len(rows))

        # Verify that the test row was processed and set back to 'pending'
        # to be processed again.
        rows = db.get_all_db_rows_by_state(self.db_session, odl_const.PENDING)
        self.assertEqual(1, len(rows))

        # Verify that _json_data was not called.
        self.assertFalse(mock_sendjson.call_count)

    def test_router_db(self):
        self._test_object_db(odl_const.ODL_ROUTER)

    def test_floatingip_db(self):
        self._test_object_db(odl_const.ODL_FLOATINGIP)

    def test_router_intf_db(self):
        # Create network, subnet and router for testing.
        kwargs = {'arg_list': (external_net.EXTERNAL,),
                  external_net.EXTERNAL: True}
        with self.network(**kwargs) as network:
            with self.subnet(cidr='10.0.0.0/24') as subnet:
                router_context, router_dict = (
                    self._get_mock_router_operation_info(network, None))
                new_router_dict = self.driver.create_router(router_context,
                                                            router_dict)
                router_id = new_router_dict['id']

                object_type = odl_const.ODL_ROUTER_INTF
                router_intf_context, router_intf_dict = \
                    self._get_mock_router_interface_operation_info(network,
                                                                   subnet)

                # Remove 'router' database entry to allow tests to pass.
                self._db_cleanup()

                # Add and test router interface 'add' database entry.
                # Note that router interface events do not generate unique
                # UUIDs.
                self.driver.add_router_interface(router_intf_context,
                                                 router_id, router_intf_dict)
                self._test_db_results(odl_const.ODL_UUID_NOT_USED,
                                      odl_const.ODL_ADD, object_type)

                # Add and test 'remove' database entry.
                self.driver.remove_router_interface(router_intf_context,
                                                    router_id,
                                                    router_intf_dict)
                self._test_db_results(odl_const.ODL_UUID_NOT_USED,
                                      odl_const.ODL_REMOVE, object_type)

    def test_router_threading(self):
        self._test_thread_processing(odl_const.ODL_ROUTER)

    def test_floatingip_threading(self):
        self._test_thread_processing(odl_const.ODL_FLOATINGIP)

    def test_router_intf_threading(self):
        # Create network, subnet and router for testing.
        kwargs = {'arg_list': (external_net.EXTERNAL,),
                  external_net.EXTERNAL: True}
        with self.network(**kwargs) as network:
            with self.subnet(cidr='10.0.0.0/24') as subnet:
                router_context, router_dict = (
                    self._get_mock_router_operation_info(network, None))
                new_router_dict = self.driver.create_router(router_context,
                                                            router_dict)
                router_id = new_router_dict['id']
                object_type = odl_const.ODL_ROUTER_INTF

                # Add and process router interface 'add' request. Adds to
                # database. Expected calls = 2 because the create_router db
                # entry is also processed.
                self._test_operation_thread_processing(
                    object_type, odl_const.ODL_ADD, network, subnet, router_id,
                    expected_calls=2)
                rows = db.get_all_db_rows_by_state(self.db_session,
                                                   odl_const.COMPLETED)
                self.assertEqual(2, len(rows))

                # Add and process 'remove' request. Adds to database.
                self._test_operation_thread_processing(
                    object_type, odl_const.ODL_REMOVE, network, subnet,
                    router_id)
                rows = db.get_all_db_rows_by_state(self.db_session,
                                                   odl_const.COMPLETED)
                self.assertEqual(3, len(rows))

    def test_delete_network_validate_ext_delete_router_dep(self):
        router_context = [NETWORK_ID]
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_NETWORK, NETWORK_ID, None,
            odl_const.ODL_DELETE, odl_const.ODL_ROUTER, ROUTER_ID,
            router_context)

    def test_create_router_validate_ext_create_port_dep(self):
        router_context = {'gw_port_id': PORT_ID}
        self._test_dependency_processing(
            odl_const.ODL_CREATE, odl_const.ODL_ROUTER, ROUTER_ID,
            router_context,
            odl_const.ODL_CREATE, odl_const.ODL_PORT, PORT_ID, None)

    def test_delete_router_validate_ext_delete_floatingip_dep(self):
        floatingip_context = [ROUTER_ID]
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_ROUTER, ROUTER_ID, None,
            odl_const.ODL_DELETE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            floatingip_context)

    def test_delete_router_validate_ext_remove_routerintf_dep(self):
        router_intf_dict = {'id': ROUTER_ID}
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_ROUTER, ROUTER_ID, None,
            odl_const.ODL_REMOVE, odl_const.ODL_ROUTER_INTF,
            odl_const.ODL_UUID_NOT_USED, router_intf_dict)

    def test_delete_router_validate_self_create_dep(self):
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_ROUTER, ROUTER_ID, EMPTY_DEP,
            odl_const.ODL_CREATE, odl_const.ODL_ROUTER, ROUTER_ID, None)

    def test_delete_router_validate_self_update_dep(self):
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_ROUTER, ROUTER_ID, EMPTY_DEP,
            odl_const.ODL_UPDATE, odl_const.ODL_ROUTER, ROUTER_ID, None)

    def test_update_router_validate_self_create_dep(self):
        router_context = {'gw_port_id': None}
        self._test_dependency_processing(
            odl_const.ODL_UPDATE, odl_const.ODL_ROUTER, ROUTER_ID,
            router_context,
            odl_const.ODL_CREATE, odl_const.ODL_ROUTER, ROUTER_ID, None)

    def test_create_floatingip_validate_ext_create_network_dep(self):
        floatingip_context = {'floating_network_id': NETWORK_ID}
        self._test_dependency_processing(
            odl_const.ODL_CREATE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            floatingip_context,
            odl_const.ODL_CREATE, odl_const.ODL_NETWORK, NETWORK_ID, None)

    def test_update_floatingip_validate_self_create_dep(self):
        floatingip_context = {'floating_network_id': NETWORK_ID}
        self._test_dependency_processing(
            odl_const.ODL_UPDATE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            floatingip_context,
            odl_const.ODL_CREATE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            EMPTY_DEP)

    def test_delete_floatingip_validate_self_create_dep(self):
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            EMPTY_DEP,
            odl_const.ODL_CREATE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            None)

    def test_delete_floatingip_validate_self_update_dep(self):
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            EMPTY_DEP,
            odl_const.ODL_UPDATE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            None)

    def test_add_router_intf_validate_ext_create_router_dep(self):
        router_intf_context = {'subnet_id': SUBNET_ID,
                               'id': ROUTER_ID}
        self._test_dependency_processing(
            odl_const.ODL_ADD, odl_const.ODL_ROUTER_INTF,
            odl_const.ODL_UUID_NOT_USED, router_intf_context,
            odl_const.ODL_CREATE, odl_const.ODL_ROUTER, ROUTER_ID, None)

    def test_add_router_intf_validate_ext_create_subnet_dep(self):
        router_intf_context = {'subnet_id': SUBNET_ID,
                               'id': ROUTER_ID}
        self._test_dependency_processing(
            odl_const.ODL_ADD, odl_const.ODL_ROUTER_INTF,
            odl_const.ODL_UUID_NOT_USED, router_intf_context,
            odl_const.ODL_CREATE, odl_const.ODL_SUBNET, SUBNET_ID, None)

    def test_remove_router_intf_validate_self_remove_router_intf_dep(self):
        router_intf_context = {'subnet_id': SUBNET_ID,
                               'id': ROUTER_ID}
        self._test_dependency_processing(
            odl_const.ODL_REMOVE, odl_const.ODL_ROUTER_INTF,
            odl_const.ODL_UUID_NOT_USED, router_intf_context,
            odl_const.ODL_ADD, odl_const.ODL_ROUTER_INTF,
            odl_const.ODL_UUID_NOT_USED, router_intf_context)
