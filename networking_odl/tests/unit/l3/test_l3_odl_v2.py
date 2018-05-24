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

import contextlib

import mock
import requests

from neutron.db import l3_db
from neutron.plugins.ml2 import plugin
from neutron.tests import base
from neutron.tests.unit.db import test_db_base_plugin_v2
from neutron.tests.unit import testlib_api
from neutron_lib.api.definitions import external_net
from neutron_lib.plugins import constants
from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_config import fixture as config_fixture
from oslo_serialization import jsonutils
from oslo_utils import uuidutils

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.common import filters
from networking_odl.db import db
from networking_odl.journal import journal
from networking_odl.l3 import l3_odl_v2
from networking_odl.ml2 import mech_driver_v2
from networking_odl.tests import base as odl_base
from networking_odl.tests.unit import test_base_db

EMPTY_DEP = {'gw_port_id': None}
FLOATINGIP_ID = uuidutils.generate_uuid()
NETWORK_ID = uuidutils.generate_uuid()
ROUTER_ID = uuidutils.generate_uuid()
SUBNET_ID = uuidutils.generate_uuid()
PORT_ID = uuidutils.generate_uuid()


class OpenDayLightMechanismConfigTests(testlib_api.SqlTestCase):
    def setUp(self):
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        self.useFixture(odl_base.OpenDaylightFeaturesFixture())
        self.cfg = self.useFixture(config_fixture.Config())
        self.useFixture(odl_base.OpenDaylightJournalThreadFixture())
        super(OpenDayLightMechanismConfigTests, self).setUp()
        self.cfg.config(mechanism_drivers=[
                        'logger', 'opendaylight_v2'], group='ml2')
        self.cfg.config(
            port_binding_controller='legacy-port-binding', group='ml2_odl')

    def _set_config(self, url='http://127.0.0.1:9999', username='someuser',
                    password='somepass'):
        self.cfg.config(url=url, group='ml2_odl')
        self.cfg.config(username=username, group='ml2_odl')
        self.cfg.config(password=password, group='ml2_odl')

    def _test_missing_config(self, **kwargs):
        self._set_config(**kwargs)
        self.assertRaisesRegex(cfg.RequiredOptError,
                               r'value required for option \w+ in group '
                               r'\[ml2_odl\]',
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
        filters.filter_for_odl(object_type, operation, self._data)

    def __eq__(self, s):
        data = jsonutils.loads(s)
        return self._data == data[self._object_type]

    def __ne__(self, s):
        return not self.__eq__(s)


class OpenDaylightL3TestCase(test_db_base_plugin_v2.NeutronDbPluginV2TestCase,
                             test_base_db.ODLBaseDbTestCase,
                             base.BaseTestCase):
    def setUp(self):
        self.cfg = self.useFixture(config_fixture.Config())
        self.cfg.config(core_plugin='neutron.plugins.ml2.plugin.Ml2Plugin')
        self.cfg.config(mechanism_drivers=[
                        'logger', 'opendaylight_v2'], group='ml2')
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        self.cfg.config(service_plugins=['odl-router_v2'])
        core_plugin = cfg.CONF.core_plugin
        service_plugins = {'l3_plugin_name': 'odl-router_v2'}
        self.useFixture(odl_base.OpenDaylightJournalThreadFixture())
        mock.patch.object(mech_driver_v2.OpenDaylightMechanismDriver,
                          '_record_in_journal').start()
        mock.patch.object(mech_driver_v2.OpenDaylightMechanismDriver,
                          'sync_from_callback_precommit').start()
        mock.patch.object(mech_driver_v2.OpenDaylightMechanismDriver,
                          'sync_from_callback_postcommit').start()
        self.useFixture(odl_base.OpenDaylightPeriodicTaskFixture())
        self.useFixture(odl_base.OpenDaylightFeaturesFixture())
        self.useFixture(odl_base.OpenDaylightPseudoAgentPrePopulateFixture())
        super(OpenDaylightL3TestCase, self).setUp(
            plugin=core_plugin, service_plugins=service_plugins)
        self.plugin = directory.get_plugin()
        self.plugin._network_is_external = mock.Mock(return_value=True)
        self.driver = directory.get_plugin(constants.L3)
        self.thread = journal.OpenDaylightJournalThread()

    @staticmethod
    def _get_mock_router_operation_info(network, subnet):
        router = {odl_const.ODL_ROUTER:
                  {'name': 'router1',
                   'admin_state_up': True,
                   'tenant_id': network['network']['tenant_id'],
                   'external_gateway_info': {'network_id':
                                             network['network']['id']}}}
        return router

    @staticmethod
    def _get_mock_floatingip_operation_info(network, subnet):
        floatingip = {odl_const.ODL_FLOATINGIP:
                      {'floating_network_id': network['network']['id'],
                       'tenant_id': network['network']['tenant_id'],
                       'subnet_id': None,
                       'floating_ip_address': None}}
        return floatingip

    @staticmethod
    def _get_mock_router_interface_operation_info(network, subnet):
        router_intf_dict = {'subnet_id': subnet['subnet']['id'],
                            'id': network['network']['id']}
        return router_intf_dict

    @classmethod
    def _get_mock_operation_info(cls, object_type, *args):
        getter = getattr(cls, '_get_mock_' + object_type + '_operation_info')
        return getter(*args)

    @classmethod
    def _get_mock_request_response(cls, status_code):
        response = mock.Mock(status_code=status_code)
        response.raise_for_status = mock.Mock() if status_code < 400 else (
            mock.Mock(side_effect=requests.exceptions.HTTPError(
                cls._status_code_msgs[status_code])))
        return response

    def _test_operation(self, status_code, expected_calls, *args, **kwargs):
        request_response = self._get_mock_request_response(status_code)
        with mock.patch('requests.sessions.Session.request',
                        return_value=request_response) as mock_method:
            self.thread.sync_pending_entries()

        if expected_calls:
            mock_method.assert_called_with(
                headers={'Content-Type': 'application/json'},
                timeout=cfg.CONF.ml2_odl.timeout, *args, **kwargs)
        self.assertEqual(expected_calls, mock_method.call_count)

    def _call_operation_object(self, operation, object_type, object_id,
                               network, subnet):
        object_dict = self._get_mock_operation_info(
            object_type, network, subnet)
        method = getattr(self.driver, operation + '_' + object_type)

        if operation == odl_const.ODL_CREATE:
            new_object_dict = method(self.db_context, object_dict)
        elif operation == odl_const.ODL_UPDATE:
            new_object_dict = method(self.db_context, object_id, object_dict)
        else:
            new_object_dict = method(self.db_context, object_id)

        return new_object_dict

    def _test_operation_thread_processing(self, object_type, operation,
                                          network, subnet, object_id,
                                          expected_calls=1):
        http_requests = {odl_const.ODL_CREATE: 'post',
                         odl_const.ODL_UPDATE: 'put',
                         odl_const.ODL_DELETE: 'delete'}
        status_codes = {odl_const.ODL_CREATE: requests.codes.created,
                        odl_const.ODL_UPDATE: requests.codes.ok,
                        odl_const.ODL_DELETE: requests.codes.no_content}

        http_request = http_requests[operation]
        status_code = status_codes[operation]

        # Create database entry.
        new_object_dict = self._call_operation_object(
            operation, object_type, object_id, network, subnet)

        # Setup expected results.
        if operation in [odl_const.ODL_UPDATE, odl_const.ODL_DELETE]:
            url = (cfg.CONF.ml2_odl.url + '/' + object_type + 's/' +
                   object_id)
        else:
            url = cfg.CONF.ml2_odl.url + '/' + object_type + 's'

        if operation in [odl_const.ODL_CREATE, odl_const.ODL_UPDATE]:
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

    @contextlib.contextmanager
    def _prepare_resource(self, resource_type):
        # Create network and subnet for testing.
        kwargs = {'arg_list': (external_net.EXTERNAL,),
                  external_net.EXTERNAL: True}
        with self.network(**kwargs) as network:
            with self.subnet(network=network):
                yield self._get_mock_operation_info(
                    resource_type, network, None)

    def _test_object_db(self, object_type):
        with self._prepare_resource(object_type) as object_dict:
            # Add and test 'create' database entry.
            method = getattr(self.driver,
                             odl_const.ODL_CREATE + '_' + object_type)
            new_object_dict = method(self.db_context, object_dict)
            object_id = new_object_dict['id']
            self._test_db_results(object_id, odl_const.ODL_CREATE, object_type)

            # Add and test 'update' database entry.
            method = getattr(self.driver,
                             odl_const.ODL_UPDATE + '_' + object_type)
            method(self.db_context, object_id, object_dict)
            self._test_db_results(object_id, odl_const.ODL_UPDATE, object_type)

            # Add and test 'delete' database entry.
            method = getattr(self.driver,
                             odl_const.ODL_DELETE + '_' + object_type)
            method(self.db_context, object_id)
            self._test_db_results(object_id, odl_const.ODL_DELETE, object_type)

    def _test_dependency_processing(
            self, test_operation, test_object, test_id, test_data,
            dep_operation, dep_object, dep_id, dep_data):

        # Mock sendjson to verify that it never gets called.
        mock_sendjson = mock.patch.object(client.OpenDaylightRestClient,
                                          'sendjson').start()

        # Create dependency db row and mark as 'processing' so it won't
        # be processed by the journal thread.
        ctxt = self.db_context
        journal.record(ctxt, dep_object, dep_id, dep_operation, dep_data)
        row = db.get_all_db_rows_by_state(self.db_session, odl_const.PENDING)
        db.update_db_row_state(self.db_session, row[0], odl_const.PROCESSING)

        # Create test row with dependent ID.
        journal.record(ctxt, test_object, test_id, test_operation, test_data)

        # Call journal thread.
        self.thread.sync_pending_entries()

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

    def test_router_threading(self):
        self._test_thread_processing(odl_const.ODL_ROUTER)

    def test_floatingip_threading(self):
        self._test_thread_processing(odl_const.ODL_FLOATINGIP)

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
            odl_const.ODL_CREATE, odl_const.ODL_PORT, PORT_ID,
            {'fixed_ips': [], 'network_id': None, odl_const.ODL_SGS: None,
             'tenant_id': 'tenant'})

    def test_delete_router_validate_ext_delete_floatingip_dep(self):
        floatingip_context = [ROUTER_ID]
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_ROUTER, ROUTER_ID, None,
            odl_const.ODL_DELETE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            floatingip_context)

    def test_delete_router_validate_self_create_dep(self):
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_ROUTER, ROUTER_ID, EMPTY_DEP,
            odl_const.ODL_CREATE, odl_const.ODL_ROUTER, ROUTER_ID, EMPTY_DEP)

    def test_delete_router_validate_self_update_dep(self):
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_ROUTER, ROUTER_ID, EMPTY_DEP,
            odl_const.ODL_UPDATE, odl_const.ODL_ROUTER, ROUTER_ID, EMPTY_DEP)

    def test_update_router_validate_self_create_dep(self):
        self._test_dependency_processing(
            odl_const.ODL_UPDATE, odl_const.ODL_ROUTER, ROUTER_ID, EMPTY_DEP,
            odl_const.ODL_CREATE, odl_const.ODL_ROUTER, ROUTER_ID, EMPTY_DEP)

    def test_create_floatingip_validate_ext_create_network_dep(self):
        floatingip_context = {'floating_network_id': NETWORK_ID}
        self._test_dependency_processing(
            odl_const.ODL_CREATE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            floatingip_context,
            odl_const.ODL_CREATE, odl_const.ODL_NETWORK, NETWORK_ID, {})

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
            {})

    def test_delete_floatingip_validate_self_update_dep(self):
        self._test_dependency_processing(
            odl_const.ODL_DELETE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            EMPTY_DEP,
            odl_const.ODL_UPDATE, odl_const.ODL_FLOATINGIP, FLOATINGIP_ID,
            {})

    @mock.patch.object(journal, 'record')
    def test__record_in_journal_retries(self, record_mock):
        self._test_retry_exceptions(
            l3_odl_v2._record_in_journal, record_mock, True)

    def _assert_record_in_journal(self, record_in_journal, resource_type,
                                  operation):
        record_in_journal.assert_called_with(
            mock.ANY, resource_type, operation, mock.ANY, mock.ANY)

    def _call_and_assert_recorded_in_journal(
            self, resource_type, operation, function, *args):
        with mock.patch.object(l3_odl_v2,
                               '_record_in_journal') as record_in_journal:
            function(self.db_context, *args)

        record_in_journal.assert_called_with(
            mock.ANY, resource_type, operation, mock.ANY, mock.ANY)

    def test_create_router_records_in_journal(self):
        with self._prepare_resource(odl_const.ODL_ROUTER) as router:
            self._call_and_assert_recorded_in_journal(
                odl_const.ODL_ROUTER, odl_const.ODL_CREATE,
                self.driver.create_router, router)

    def test_update_router_records_in_journal(self):
        with self._prepare_resource(odl_const.ODL_ROUTER) as router:
            result = self.driver.create_router(self.db_context, router)
            self._call_and_assert_recorded_in_journal(
                odl_const.ODL_ROUTER, odl_const.ODL_UPDATE,
                self.driver.update_router, result['id'], router)

    def test_delete_router_records_in_journal(self):
        with self._prepare_resource(odl_const.ODL_ROUTER) as router:
            result = self.driver.create_router(self.db_context, router)
            self._call_and_assert_recorded_in_journal(
                odl_const.ODL_ROUTER, odl_const.ODL_DELETE,
                self.driver.delete_router, result['id'])

    def test_create_fip_records_in_journal(self):
        with self._prepare_resource(odl_const.ODL_FLOATINGIP) as fip:
            self._call_and_assert_recorded_in_journal(
                odl_const.ODL_FLOATINGIP, odl_const.ODL_CREATE,
                self.driver.create_floatingip, fip)

    def test_update_fip_records_in_journal(self):
        with self._prepare_resource(odl_const.ODL_FLOATINGIP) as fip:
            result = self.driver.create_floatingip(self.db_context, fip)
            self._call_and_assert_recorded_in_journal(
                odl_const.ODL_FLOATINGIP, odl_const.ODL_UPDATE,
                self.driver.update_floatingip, result['id'], fip)

    def test_delete_fip_records_in_journal(self):
        with self._prepare_resource(odl_const.ODL_FLOATINGIP) as fip:
            result = self.driver.create_floatingip(self.db_context, fip)
            self._call_and_assert_recorded_in_journal(
                odl_const.ODL_FLOATINGIP, odl_const.ODL_DELETE,
                self.driver.delete_floatingip, result['id'])

    @mock.patch.object(l3_db.L3_NAT_dbonly_mixin, 'disassociate_floatingips')
    @mock.patch.object(l3_odl_v2.OpenDaylightL3RouterPlugin, 'get_floatingips')
    def test_disassociate_floatingips_records_in_journal(
            self, get_fips, disassociate_floatingips):
        with self._prepare_resource(odl_const.ODL_FLOATINGIP) as fip:
            result = self.driver.create_floatingip(self.db_context, fip)
            get_fips.return_value = [result]
            self._call_and_assert_recorded_in_journal(
                odl_const.ODL_FLOATINGIP, odl_const.ODL_UPDATE,
                self.driver.disassociate_floatingips, 'fake_id')

        self.assertTrue(disassociate_floatingips.called)
