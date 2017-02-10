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
import copy
import datetime
import mock
import operator
import requests
import testscenarios

from neutron.db import api as neutron_db_api
from neutron.db.models import securitygroup
from neutron.extensions import multiprovidernet as mpnet
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import plugin
from neutron.tests.unit.plugins.ml2 import test_plugin
from neutron.tests.unit import testlib_api
from neutron_lib.api.definitions import provider_net as providernet
from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_serialization import jsonutils

from networking_odl.common import callback
from networking_odl.common import constants as odl_const
from networking_odl.common import filters
from networking_odl.common import utils
from networking_odl.db import db
from networking_odl.journal import cleanup
from networking_odl.journal import journal
from networking_odl.journal import maintenance
from networking_odl.ml2 import mech_driver_v2
from networking_odl.tests.unit import base_v2


# Required to generate tests from scenarios. Not compatible with nose.
load_tests = testscenarios.load_tests_apply_scenarios

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')

SECURITY_GROUP = '2f9244b4-9bee-4e81-bc4a-3f3c2045b3d7'
SG_FAKE_ID = 'sg_fake_uuid'
SG_RULE_FAKE_ID = 'sg_rule_fake_uuid'


class OpenDayLightMechanismConfigTests(testlib_api.SqlTestCase):
    def setUp(self):
        super(OpenDayLightMechanismConfigTests, self).setUp()
        self.mock_sync_thread = mock.patch.object(
            journal.OpendaylightJournalThread, 'start_odl_sync_thread').start()
        self.mock_mt_thread = mock.patch.object(
            maintenance.MaintenanceThread, 'start').start()
        cfg.CONF.set_override('mechanism_drivers',
                              ['logger', 'opendaylight_v2'], 'ml2')
        cfg.CONF.set_override('port_binding_controller',
                              'legacy-port-binding', 'ml2_odl')

    def _set_config(self, url='http://127.0.0.1:9999', username='someuser',
                    password='somepass'):
        cfg.CONF.set_override('url', url, 'ml2_odl')
        cfg.CONF.set_override('username', username, 'ml2_odl')
        cfg.CONF.set_override('password', password, 'ml2_odl')

    def _test_missing_config(self, **kwargs):
        self._set_config(**kwargs)
        self.assertRaisesRegex(cfg.RequiredOptError,
                               'value required for option \w+ in group '
                               '\[ml2_odl\]',
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


class OpenDaylightMechanismTestBasicGet(test_plugin.TestMl2BasicGet,
                                        base_v2.OpenDaylightTestCase):
    pass


class OpenDaylightMechanismTestNetworksV2(test_plugin.TestMl2NetworksV2,
                                          base_v2.OpenDaylightTestCase):
    pass


class OpenDaylightMechanismTestSubnetsV2(test_plugin.TestMl2SubnetsV2,
                                         base_v2.OpenDaylightTestCase):
    pass


class OpenDaylightMechanismTestPortsV2(test_plugin.TestMl2PortsV2,
                                       base_v2.OpenDaylightTestCase):
    pass


class DataMatcher(object):

    def __init__(self, operation, object_type, context):
        if object_type in [odl_const.ODL_SG, odl_const.ODL_SG_RULE]:
            self._data = copy.deepcopy(context[object_type])
        elif object_type == odl_const.ODL_PORT:
            # NOTE(yamahata): work around for journal._enrich_port()
            self._data = copy.deepcopy(context.current)
            if self._data.get(odl_const.ODL_SGS):
                self._data[odl_const.ODL_SGS] = [
                    {'id': id_} for id_ in self._data[odl_const.ODL_SGS]]
        else:
            self._data = copy.deepcopy(context.current)
        self._object_type = object_type
        filters.filter_for_odl(object_type, operation, self._data)

    def __eq__(self, s):
        data = jsonutils.loads(s)
        return self._data == data[self._object_type]

    def __ne__(self, s):
        return not self.__eq__(s)

    def __repr__(self):
        # for debugging
        return 'DataMatcher(%(object_type)s, %(data)s)' % {
            'object_type': self._object_type,
            'data': self._data}


class AttributeDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttributeDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class OpenDaylightMechanismDriverTestCase(base_v2.OpenDaylightConfigBase):
    def setUp(self):
        super(OpenDaylightMechanismDriverTestCase, self).setUp()
        self.db_session = neutron_db_api.get_session()
        self.mech = mech_driver_v2.OpenDaylightMechanismDriver()
        self.mech.initialize()
        self.thread = journal.OpendaylightJournalThread()

    @staticmethod
    def _get_mock_network_operation_context():
        current = {'status': 'ACTIVE',
                   'subnets': [],
                   'name': 'net1',
                   'provider:physical_network': None,
                   'admin_state_up': True,
                   'tenant_id': 'test-tenant',
                   'provider:network_type': 'local',
                   'router:external': False,
                   'shared': False,
                   'id': 'd897e21a-dfd6-4331-a5dd-7524fa421c3e',
                   'provider:segmentation_id': None}
        context = mock.Mock(current=current)
        context._plugin_context.session = neutron_db_api.get_session()
        return context

    @staticmethod
    def _get_mock_subnet_operation_context():
        current = {'ipv6_ra_mode': None,
                   'allocation_pools': [{'start': '10.0.0.2',
                                         'end': '10.0.1.254'}],
                   'host_routes': [],
                   'ipv6_address_mode': None,
                   'cidr': '10.0.0.0/23',
                   'id': '72c56c48-e9b8-4dcf-b3a7-0813bb3bd839',
                   'name': '',
                   'enable_dhcp': True,
                   'network_id': 'd897e21a-dfd6-4331-a5dd-7524fa421c3e',
                   'tenant_id': 'test-tenant',
                   'dns_nameservers': [],
                   'gateway_ip': '10.0.0.1',
                   'ip_version': 4,
                   'shared': False}
        context = mock.Mock(current=current)
        context._plugin_context.session = neutron_db_api.get_session()
        return context

    @staticmethod
    def _get_mock_port_operation_context():
        current = {'status': 'DOWN',
                   'binding:host_id': '',
                   'allowed_address_pairs': [],
                   'device_owner': 'fake_owner',
                   'binding:profile': {},
                   'fixed_ips': [{
                       'subnet_id': '72c56c48-e9b8-4dcf-b3a7-0813bb3bd839'}],
                   'id': '83d56c48-e9b8-4dcf-b3a7-0813bb3bd940',
                   'security_groups': [SECURITY_GROUP],
                   'device_id': 'fake_device',
                   'name': '',
                   'admin_state_up': True,
                   'network_id': 'd897e21a-dfd6-4331-a5dd-7524fa421c3e',
                   'tenant_id': 'test-tenant',
                   'binding:vif_details': {},
                   'binding:vnic_type': 'normal',
                   'binding:vif_type': 'unbound',
                   'mac_address': '12:34:56:78:21:b6'}
        _network = OpenDaylightMechanismDriverTestCase.\
            _get_mock_network_operation_context().current
        _plugin = directory.get_plugin()
        _plugin.get_security_group = mock.Mock(return_value=SECURITY_GROUP)
        _plugin.get_port = mock.Mock(return_value=current)
        _plugin.get_network = mock.Mock(return_value=_network)
        _plugin_context_mock = {'session': neutron_db_api.get_session()}
        _network_context_mock = {'_network': _network}
        context = {'current': AttributeDict(current),
                   '_plugin': _plugin,
                   '_plugin_context': AttributeDict(_plugin_context_mock),
                   '_network_context': AttributeDict(_network_context_mock)}
        return AttributeDict(context)

    @staticmethod
    def _get_mock_security_group_operation_context():
        context = {odl_const.ODL_SG: {'name': 'test_sg',
                                      'project_id': 'test-tenant',
                                      'tenant_id': 'test-tenant',
                                      'description': 'test-description',
                                      'rules': [],
                                      'id': SG_FAKE_ID}}
        return context

    @staticmethod
    def _get_mock_security_group_rule_operation_context():
        context = {odl_const.ODL_SG_RULE: {'security_group_id': SG_FAKE_ID,
                                           'id': SG_RULE_FAKE_ID}}
        return context

    @classmethod
    def _get_mock_operation_context(cls, object_type):
        getter = getattr(cls, '_get_mock_%s_operation_context' % object_type)
        return getter()

    _status_code_msgs = {
        200: '',
        201: '',
        204: '',
        400: '400 Client Error: Bad Request',
        401: '401 Client Error: Unauthorized',
        403: '403 Client Error: Forbidden',
        404: '404 Client Error: Not Found',
        409: '409 Client Error: Conflict',
        501: '501 Server Error: Not Implemented',
        503: '503 Server Error: Service Unavailable',
    }

    @classmethod
    def _get_mock_request_response(cls, status_code):
        response = mock.Mock(status_code=status_code)
        response.raise_for_status = mock.Mock() if status_code < 400 else (
            mock.Mock(side_effect=requests.exceptions.HTTPError(
                cls._status_code_msgs[status_code])))
        return response

    def _test_operation(self, method, status_code, expected_calls,
                        *args, **kwargs):
        request_response = self._get_mock_request_response(status_code)
        with mock.patch('requests.request',
                        return_value=request_response) as mock_method:
            method(exit_after_run=True)

        if expected_calls:
            mock_method.assert_called_with(
                headers={'Content-Type': 'application/json'},
                auth=(cfg.CONF.ml2_odl.username, cfg.CONF.ml2_odl.password),
                timeout=cfg.CONF.ml2_odl.timeout, *args, **kwargs)
        self.assertEqual(expected_calls, mock_method.call_count)

    def _call_operation_object(self, operation, object_type):
        context = self._get_mock_operation_context(object_type)

        if object_type in [odl_const.ODL_SG, odl_const.ODL_SG_RULE]:
            plugin_context_mock = mock.Mock()
            plugin_context_mock.session = neutron_db_api.get_session()
            res_type = [rt for rt in callback._RESOURCE_MAPPING.values()
                        if rt.singular == object_type][0]
            res_id = context[object_type]['id']
            context_ = (copy.deepcopy(context)
                        if operation != odl_const.ODL_DELETE else None)
            if (object_type == odl_const.ODL_SG and
                    operation in [odl_const.ODL_CREATE, odl_const.ODL_DELETE]):
                # TODO(yamahata): remove this work around once
                # https://review.openstack.org/#/c/281693/
                # is merged.
                if operation == odl_const.ODL_CREATE:
                    sg = securitygroup.SecurityGroup(
                        id=res_id, name=context_[object_type]['name'],
                        tenant_id=context_[object_type]['tenant_id'],
                        description=context_[object_type]['description'])
                    plugin_context_mock.session.add(sg)
                    context_[odl_const.ODL_SG].pop('id', None)
                if operation == odl_const.ODL_DELETE:
                    sg = mock.Mock()
                    sg.rules = []
                self.mech.sync_from_callback_precommit(
                    plugin_context_mock, operation, res_type, res_id, context_,
                    security_group=sg)
            else:
                self.mech.sync_from_callback_precommit(
                    plugin_context_mock, operation, res_type, res_id, context_)
        else:
            method = getattr(self.mech, '%s_%s_precommit' % (operation,
                                                             object_type))
            method(context)

    def _test_operation_object(self, operation, object_type):
        self._call_operation_object(operation, object_type)

        context = self._get_mock_operation_context(object_type)
        row = db.get_oldest_pending_db_row_with_lock(self.db_session)
        self.assertEqual(operation, row['operation'])
        self.assertEqual(object_type, row['object_type'])
        self.assertEqual(context.current['id'], row['object_uuid'])

    def _test_thread_processing(self, operation, object_type,
                                expected_calls=1):
        http_requests = {odl_const.ODL_CREATE: 'post',
                         odl_const.ODL_UPDATE: 'put',
                         odl_const.ODL_DELETE: 'delete'}
        status_codes = {odl_const.ODL_CREATE: requests.codes.created,
                        odl_const.ODL_UPDATE: requests.codes.ok,
                        odl_const.ODL_DELETE: requests.codes.no_content}

        http_request = http_requests[operation]
        status_code = status_codes[operation]

        self._call_operation_object(operation, object_type)

        context = self._get_mock_operation_context(object_type)
        url_object_type = utils.neutronify(object_type)
        if operation in [odl_const.ODL_UPDATE, odl_const.ODL_DELETE]:
            if object_type in [odl_const.ODL_SG, odl_const.ODL_SG_RULE]:
                uuid = context[object_type]['id']
            else:
                uuid = context.current['id']
            url = '%s/%ss/%s' % (cfg.CONF.ml2_odl.url, url_object_type, uuid)
        else:
            url = '%s/%ss' % (cfg.CONF.ml2_odl.url, url_object_type)

        if (object_type == odl_const.ODL_SG and
                operation == odl_const.ODL_CREATE):
            context = copy.deepcopy(context)
            context[odl_const.ODL_SG].pop('rules')
        if operation in [odl_const.ODL_CREATE, odl_const.ODL_UPDATE]:
            kwargs = {
                'url': url,
                'data': DataMatcher(operation, object_type, context)}
        else:
            kwargs = {'url': url, 'data': None}
        with mock.patch.object(self.thread.event, 'wait',
                               return_value=False):
            self._test_operation(self.thread.run_sync_thread, status_code,
                                 expected_calls, http_request, **kwargs)

    def _test_object_type(self, object_type):
        # Add and process create request.
        self._test_thread_processing(odl_const.ODL_CREATE, object_type)
        rows = db.get_all_db_rows_by_state(self.db_session,
                                           odl_const.COMPLETED)
        self.assertEqual(1, len(rows))

        # Add and process update request. Adds to database.
        self._test_thread_processing(odl_const.ODL_UPDATE, object_type)
        rows = db.get_all_db_rows_by_state(self.db_session,
                                           odl_const.COMPLETED)
        self.assertEqual(2, len(rows))

        # Add and process update request. Adds to database.
        self._test_thread_processing(odl_const.ODL_DELETE, object_type)
        rows = db.get_all_db_rows_by_state(self.db_session,
                                           odl_const.COMPLETED)
        self.assertEqual(3, len(rows))

    def _test_object_type_pending_network(self, object_type):
        # Create a network (creates db row in pending state).
        self._call_operation_object(odl_const.ODL_CREATE,
                                    odl_const.ODL_NETWORK)

        # Create object_type database row and process. This results in both
        # the object_type and network rows being processed.
        self._test_thread_processing(odl_const.ODL_CREATE, object_type,
                                     expected_calls=2)

        # Verify both rows are now marked as completed.
        rows = db.get_all_db_rows_by_state(self.db_session,
                                           odl_const.COMPLETED)
        self.assertEqual(2, len(rows))

    def _test_object_type_processing_network(self, object_type):
        self._test_object_operation_pending_another_object_operation(
            object_type, odl_const.ODL_CREATE, odl_const.ODL_NETWORK,
            odl_const.ODL_CREATE)

    def _test_object_operation_pending_object_operation(
            self, object_type, operation, pending_operation):
        self._test_object_operation_pending_another_object_operation(
            object_type, operation, object_type, pending_operation)

    def _test_object_operation_pending_another_object_operation(
            self, object_type, operation, pending_type, pending_operation):
        # Create the object_type (creates db row in pending state).
        self._call_operation_object(pending_operation,
                                    pending_type)

        # Get pending row and mark as processing so that
        # this row will not be processed by journal thread.
        row = db.get_all_db_rows_by_state(self.db_session, odl_const.PENDING)
        db.update_db_row_state(self.db_session, row[0], odl_const.PROCESSING)

        # Create the object_type database row and process.
        # Verify that object request is not processed because the
        # dependent object operation has not been marked as 'completed'.
        self._test_thread_processing(operation,
                                     object_type,
                                     expected_calls=0)

        # Verify that all rows are still in the database.
        rows = db.get_all_db_rows_by_state(self.db_session,
                                           odl_const.PROCESSING)
        self.assertEqual(1, len(rows))
        rows = db.get_all_db_rows_by_state(self.db_session, odl_const.PENDING)
        self.assertEqual(1, len(rows))

    def _test_parent_delete_pending_child_delete(self, parent, child):
        self._test_object_operation_pending_another_object_operation(
            parent, odl_const.ODL_DELETE, child, odl_const.ODL_DELETE)

    def _test_cleanup_processing_rows(self, last_retried, expected_state):
        # Create a dummy network (creates db row in pending state).
        self._call_operation_object(odl_const.ODL_CREATE,
                                    odl_const.ODL_NETWORK)

        # Get pending row and mark as processing and update
        # the last_retried time
        row = db.get_all_db_rows_by_state(self.db_session,
                                          odl_const.PENDING)[0]
        row.last_retried = last_retried
        db.update_db_row_state(self.db_session, row, odl_const.PROCESSING)

        # Test if the cleanup marks this in the desired state
        # based on the last_retried timestamp
        cleanup.JournalCleanup().cleanup_processing_rows(self.db_session)

        # Verify that the Db row is in the desired state
        rows = db.get_all_db_rows_by_state(self.db_session, expected_state)
        self.assertEqual(1, len(rows))

    def test_driver(self):
        for operation in [odl_const.ODL_CREATE, odl_const.ODL_UPDATE,
                          odl_const.ODL_DELETE]:
            for object_type in [odl_const.ODL_NETWORK, odl_const.ODL_SUBNET,
                                odl_const.ODL_PORT]:
                self._test_operation_object(operation, object_type)

    def test_port_precommit_no_tenant(self):
        context = self._get_mock_operation_context(odl_const.ODL_PORT)
        context.current['tenant_id'] = ''

        method = getattr(self.mech, 'create_port_precommit')
        method(context)

        # Verify that the Db row has a tenant
        rows = db.get_all_db_rows_by_state(self.db_session, odl_const.PENDING)
        self.assertEqual(1, len(rows))
        _network = OpenDaylightMechanismDriverTestCase.\
            _get_mock_network_operation_context().current
        self.assertEqual(_network['tenant_id'], rows[0]['data']['tenant_id'])

    def test_network(self):
        self._test_object_type(odl_const.ODL_NETWORK)

    def test_network_update_pending_network_create(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_NETWORK, odl_const.ODL_UPDATE, odl_const.ODL_CREATE)

    def test_network_delete_pending_network_create(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_NETWORK, odl_const.ODL_DELETE, odl_const.ODL_CREATE)

    def test_network_delete_pending_network_update(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_NETWORK, odl_const.ODL_DELETE, odl_const.ODL_UPDATE)

    def test_network_delete_pending_subnet_delete(self):
        self._test_parent_delete_pending_child_delete(
            odl_const.ODL_NETWORK, odl_const.ODL_SUBNET)

    def test_network_delete_pending_port_delete(self):
        self._test_parent_delete_pending_child_delete(
            odl_const.ODL_NETWORK, odl_const.ODL_PORT)

    def test_subnet(self):
        self._test_object_type(odl_const.ODL_SUBNET)

    def test_subnet_update_pending_subnet_create(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_SUBNET, odl_const.ODL_UPDATE, odl_const.ODL_CREATE)

    def test_subnet_delete_pending_subnet_create(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_SUBNET, odl_const.ODL_DELETE, odl_const.ODL_CREATE)

    def test_subnet_delete_pending_subnet_update(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_SUBNET, odl_const.ODL_DELETE, odl_const.ODL_UPDATE)

    def test_subnet_pending_network(self):
        self._test_object_type_pending_network(odl_const.ODL_SUBNET)

    def test_subnet_processing_network(self):
        self._test_object_type_processing_network(odl_const.ODL_SUBNET)

    def test_subnet_delete_pending_port_delete(self):
        self._test_parent_delete_pending_child_delete(
            odl_const.ODL_SUBNET, odl_const.ODL_PORT)

    def test_port(self):
        self._test_object_type(odl_const.ODL_PORT)

    def test_port_update_pending_port_create(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_PORT, odl_const.ODL_UPDATE, odl_const.ODL_CREATE)

    def test_port_delete_pending_port_create(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_PORT, odl_const.ODL_DELETE, odl_const.ODL_CREATE)

    def test_port_delete_pending_port_update(self):
        self._test_object_operation_pending_object_operation(
            odl_const.ODL_PORT, odl_const.ODL_DELETE, odl_const.ODL_UPDATE)

    def test_port_pending_network(self):
        self._test_object_type_pending_network(odl_const.ODL_PORT)

    def test_port_processing_network(self):
        self._test_object_type_processing_network(odl_const.ODL_PORT)

    def test_cleanup_processing_rows_time_not_expired(self):
        self._test_cleanup_processing_rows(datetime.datetime.utcnow(),
                                           odl_const.PROCESSING)

    def test_cleanup_processing_rows_time_expired(self):
        old_time = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        self._test_cleanup_processing_rows(old_time, odl_const.PENDING)

    def test_thread_call(self):
        """Verify that the sync thread method is called."""

        # Create any object that would spin up the sync thread via the
        # decorator call_thread_on_end() used by all the event handlers.
        self._call_operation_object(odl_const.ODL_CREATE,
                                    odl_const.ODL_NETWORK)

        # Verify that the thread call was made.
        self.assertTrue(self.mock_sync_thread.called)

    def test_sg(self):
        self._test_object_type(odl_const.ODL_SG)

    def test_sg_rule(self):
        self._test_object_type(odl_const.ODL_SG_RULE)

    def test_sg_delete(self):
        with mock.patch.object(journal, 'record') as record:
            context = self._get_mock_operation_context(odl_const.ODL_SG)
            res_id = context[odl_const.ODL_SG]['id']
            plugin_context_mock = mock.Mock()
            plugin_context_mock.session = neutron_db_api.get_session()
            rule = mock.Mock()
            rule.id = SG_RULE_FAKE_ID
            rule.security_group_id = SG_FAKE_ID
            sg = mock.Mock()
            sg.id = SG_FAKE_ID
            sg.rules = [rule]
            kwargs = {'security_group': sg}
            self.mech.sync_from_callback_precommit(
                plugin_context_mock, odl_const.ODL_DELETE,
                callback._RESOURCE_MAPPING[odl_const.ODL_SG],
                res_id, context, **kwargs)
            record.assert_has_calls(
                [mock.call(mock.ANY, None, 'security_group', 'sg_fake_uuid',
                           'delete',
                           {'description': 'test-description',
                            'project_id': 'test-tenant',
                            'rules': [],
                            'tenant_id': 'test-tenant',
                            'id': 'sg_fake_uuid', 'name': 'test_sg'}),
                 mock.call(mock.ANY, None, 'security_group_rule',
                           'sg_rule_fake_uuid', 'delete', ['sg_fake_uuid'])])

    def test_sync_multiple_updates(self):
        # add 2 updates
        for i in range(2):
            self._call_operation_object(odl_const.ODL_UPDATE,
                                        odl_const.ODL_NETWORK)

        # get the last update row
        rows = db.get_all_db_rows(self.db_session)
        rows.sort(key=operator.attrgetter("seqnum"))
        first_row = rows[0]

        # change the state to processing
        db.update_db_row_state(self.db_session, first_row,
                               odl_const.PROCESSING)

        # create 1 more operation to trigger the sync thread
        # verify that there are no calls to ODL controller, because the
        # first row was processing (exit_after_run = true)
        self._test_thread_processing(odl_const.ODL_UPDATE,
                                     odl_const.ODL_NETWORK, expected_calls=0)

        # validate that all the pending rows stays in 'pending' state
        # first row should be 'processing' because it was not processed
        processing = db.get_all_db_rows_by_state(self.db_session, 'processing')
        self.assertEqual(1, len(processing))
        rows = db.get_all_db_rows_by_state(self.db_session, 'pending')
        self.assertEqual(2, len(rows))


class _OpenDaylightDriverVlanTransparencyBase(base_v2.OpenDaylightTestCase):
    def _driver_context(self, network):
        return mock.MagicMock(current=network)


class TestOpenDaylightDriverVlanTransparencyNetwork(
        _OpenDaylightDriverVlanTransparencyBase):
    def _test_network_type(self, expected, network_type):
        context = self._driver_context({providernet.NETWORK_TYPE:
                                        network_type})
        self.assertEqual(expected,
                         self.mech.check_vlan_transparency(context))

    def test_none_network_type(self):
        context = self._driver_context({})
        self.assertTrue(self.mech.check_vlan_transparency(context))

    def test_vlan_transparency(self):
        for network_type in [p_const.TYPE_VXLAN]:
            self._test_network_type(True, network_type)
        for network_type in [p_const.TYPE_FLAT, p_const.TYPE_GENEVE,
                             p_const.TYPE_GRE, p_const.TYPE_LOCAL,
                             p_const.TYPE_VLAN]:
            self._test_network_type(False, network_type)


class TestOpenDaylightDriverVlanTransparency(
        _OpenDaylightDriverVlanTransparencyBase):
    scenarios = [
        ("vxlan_vxlan",
         {'expected': True,
          'network_types': [p_const.TYPE_VXLAN, p_const.TYPE_VXLAN]}),
        ("gre_vxlan",
         {'expected': False,
          'network_types': [p_const.TYPE_GRE, p_const.TYPE_VXLAN]}),
        ("vxlan_vlan",
         {'expected': False,
          'network_types': [p_const.TYPE_VXLAN, p_const.TYPE_VLAN]}),
        ("vxlan_flat",
         {'expected': False,
          'network_types': [p_const.TYPE_VXLAN, p_const.TYPE_FLAT]}),
        ("vlan_vlan",
         {'expected': False,
          'network_types': [p_const.TYPE_VLAN, p_const.TYPE_VLAN]}),
    ]

    def test_network_segments(self):
        segments = [{providernet.NETWORK_TYPE: type_}
                    for type_ in self.network_types]
        context = self._driver_context({mpnet.SEGMENTS: segments})
        self.assertEqual(self.expected,
                         self.mech.check_vlan_transparency(context))
