# Copyright (c) 2013-2014 OpenStack Foundation
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
import mock
import socket

from oslo_config import cfg
from oslo_serialization import jsonutils
import requests
import webob.exc

from neutron.common import constants as n_constants
from neutron.extensions import portbindings
from neutron.plugins.common import constants
from neutron.plugins.ml2 import config as config
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2 import driver_context as driver_context
from neutron.plugins.ml2 import plugin
from neutron.tests import base
from neutron.tests.unit.plugins.ml2 import test_plugin
from neutron.tests.unit import testlib_api

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.ml2 import legacy_port_binding
from networking_odl.ml2 import mech_driver
from networking_odl.ml2 import network_topology


cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')


HOST = 'fake-host'
PLUGIN_NAME = 'neutron.plugins.ml2.plugin.Ml2Plugin'
FAKE_NETWORK = {'status': 'ACTIVE',
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

FAKE_SUBNET = {'ipv6_ra_mode': None,
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

FAKE_PORT = {'status': 'DOWN',
             'binding:host_id': '',
             'allowed_address_pairs': [],
             'device_owner': 'fake_owner',
             'binding:profile': {},
             'fixed_ips': [],
             'id': '72c56c48-e9b8-4dcf-b3a7-0813bb3bd839',
             'security_groups': [],
             'device_id': 'fake_device',
             'name': '',
             'admin_state_up': True,
             'network_id': 'c13bba05-eb07-45ba-ace2-765706b2d701',
             'tenant_id': 'bad_tenant_id',
             'binding:vif_details': {},
             'binding:vnic_type': 'normal',
             'binding:vif_type': 'unbound',
             'mac_address': '12:34:56:78:21:b6'}

FAKE_SECURITY_GROUP = {'description': 'Default security group',
                       'id': '6875fc07-853f-4230-9ab9-23d1af894240',
                       'name': 'default',
                       'security_group_rules': [],
                       'tenant_id': '04bb5f9a0fa14ad18203035c791ffae2'}

FAKE_SECURITY_GROUP_RULE = {'direction': 'ingress',
                            'ethertype': 'IPv4',
                            'id': '399029df-cefe-4a7a-b6d6-223558627d23',
                            'port_range_max': 0,
                            'port_range_min': 0,
                            'protocol': 0,
                            'remote_group_id': '6875fc07-853f-4230-9ab9',
                            'remote_ip_prefix': 0,
                            'security_group_id': '6875fc07-853f-4230-9ab9',
                            'tenant_id': '04bb5f9a0fa14ad18203035c791ffae2'}


class OpenDaylightTestCase(test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight']

    def setUp(self):
        # Set URL/user/pass so init doesn't throw a cfg required error.
        # They are not used in these tests since sendjson is overwritten.
        config.cfg.CONF.set_override('url', 'http://127.0.0.1:9999', 'ml2_odl')
        config.cfg.CONF.set_override('username', 'someuser', 'ml2_odl')
        config.cfg.CONF.set_override('password', 'somepass', 'ml2_odl')

        super(OpenDaylightTestCase, self).setUp()
        self.port_create_status = 'DOWN'
        self.mech = mech_driver.OpenDaylightMechanismDriver()
        mock.patch.object(
            client.OpenDaylightRestClient,
            'sendjson',
            new=self.check_sendjson).start()

        # Prevent test from accidentally connecting to any web service
        mock.patch.object(
            network_topology, 'NetworkTopologyClient',
            return_value=mock.Mock(
                specs=network_topology.NetworkTopologyClient,
                get=mock.Mock(side_effect=requests.HTTPError))).start()

        # Prevent hosts resolution from changing the behaviour of tests
        mock.patch.object(
            network_topology.utils,
            'get_addresses_by_name',
            side_effect=socket.gaierror).start()

    def check_sendjson(self, method, urlpath, obj):
        self.assertFalse(urlpath.startswith("http://"))


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


class OpenDaylightMechanismTestBasicGet(test_plugin.TestMl2BasicGet,
                                        OpenDaylightTestCase):
    pass


class OpenDaylightMechanismTestNetworksV2(test_plugin.TestMl2NetworksV2,
                                          OpenDaylightTestCase):
    pass


class OpenDaylightMechanismTestSubnetsV2(test_plugin.TestMl2SubnetsV2,
                                         OpenDaylightTestCase):
    pass


class OpenDaylightMechanismTestPortsV2(test_plugin.TestMl2PortsV2,
                                       OpenDaylightTestCase):

    def setUp(self):
        mock.patch.object(
            mech_driver.OpenDaylightDriver,
            'out_of_sync',
            new_callable=mock.PropertyMock(return_value=False)).start()
        super(OpenDaylightMechanismTestPortsV2, self).setUp()

    def test_update_port_mac(self):
        self.check_update_port_mac(
            host_arg={portbindings.HOST_ID: HOST},
            arg_list=(portbindings.HOST_ID,),
            expected_status=webob.exc.HTTPConflict.code,
            expected_error='PortBound')

    def test_create_router_port_and_fail_create_postcommit(self):
        # Skip this test case for now as a workaround.
        # TODO(rzang): remove this once [1] gets in.
        # [1]https://review.openstack.org/#/c/310682/
        self.skipTest("skip as a workaround")


class DataMatcher(object):

    def __init__(self, operation, object_type, context):
        self._data = context.current.copy()
        self._object_type = object_type
        filter_cls = mech_driver.OpenDaylightDriver.FILTER_MAP[
            '%ss' % object_type]
        attr_filter = getattr(filter_cls, 'filter_%s_attributes' % operation)
        attr_filter(self._data, context)

    def __eq__(self, s):
        data = jsonutils.loads(s)
        return self._data == data[self._object_type]


class OpenDaylightSyncTestCase(OpenDaylightTestCase):

    def setUp(self):
        super(OpenDaylightSyncTestCase, self).setUp()
        self.given_back_end = mech_driver.OpenDaylightDriver()

    def test_simple_sync_all_with_HTTPError_not_found(self):
        self.given_back_end.out_of_sync = True
        ml2_plugin = plugin.Ml2Plugin()

        response = mock.Mock(status_code=requests.codes.not_found)
        fake_exception = requests.exceptions.HTTPError('Test',
                                                       response=response)

        def side_eff(*args, **kwargs):
            # HTTP ERROR exception with 404 status code will be raised when use
            # sendjson to get the object in ODL DB
            if args[0] == 'get':
                raise fake_exception

        with mock.patch.object(client.OpenDaylightRestClient, 'sendjson',
                               side_effect=side_eff), \
            mock.patch.object(plugin.Ml2Plugin, 'get_networks',
                              return_value=[FAKE_NETWORK.copy()]), \
            mock.patch.object(plugin.Ml2Plugin, 'get_network',
                              return_value=FAKE_NETWORK.copy()), \
            mock.patch.object(plugin.Ml2Plugin, 'get_subnets',
                              return_value=[FAKE_SUBNET.copy()]), \
            mock.patch.object(plugin.Ml2Plugin, 'get_ports',
                              return_value=[FAKE_PORT.copy()]), \
            mock.patch.object(plugin.Ml2Plugin, 'get_security_groups',
                              return_value=[FAKE_SECURITY_GROUP.copy()]), \
            mock.patch.object(plugin.Ml2Plugin, 'get_security_group_rules',
                              return_value=[FAKE_SECURITY_GROUP_RULE.copy()]):
            self.given_back_end.sync_full(ml2_plugin)

            sync_id_list = [FAKE_NETWORK['id'], FAKE_SUBNET['id'],
                            FAKE_PORT['id'],
                            FAKE_SECURITY_GROUP['id'],
                            FAKE_SECURITY_GROUP_RULE['id']]

            act = []
            for args, kwargs in \
                client.OpenDaylightRestClient.sendjson.call_args_list:
                if args[0] == 'post':
                    for key in args[2]:
                        act.append(args[2][key][0]['id'])
            self.assertEqual(act, sync_id_list)

    def test_simple_sync_all_with_all_synced(self):
        self.given_back_end.out_of_sync = True
        ml2_plugin = plugin.Ml2Plugin()

        with mock.patch.object(client.OpenDaylightRestClient, 'sendjson',
                               return_value=None), \
            mock.patch.object(plugin.Ml2Plugin, 'get_networks',
                              return_value=[FAKE_NETWORK.copy()]), \
            mock.patch.object(plugin.Ml2Plugin, 'get_subnets',
                              return_value=[FAKE_SUBNET.copy()]), \
            mock.patch.object(plugin.Ml2Plugin, 'get_ports',
                              return_value=[FAKE_PORT.copy()]), \
            mock.patch.object(plugin.Ml2Plugin, 'get_security_groups',
                              return_value=[FAKE_SECURITY_GROUP.copy()]), \
            mock.patch.object(plugin.Ml2Plugin, 'get_security_group_rules',
                              return_value=[FAKE_SECURITY_GROUP_RULE.copy()]):
            self.given_back_end.sync_full(ml2_plugin)

            # it's only called for GET, there is no call for PUT
            # 5 = network, subnet, port, security_group, security_group_rule
            self.assertEqual(5,
                             client.OpenDaylightRestClient.sendjson.call_count)


class OpenDaylightMechanismDriverTestCase(base.BaseTestCase):

    def setUp(self):
        super(OpenDaylightMechanismDriverTestCase, self).setUp()
        config.cfg.CONF.set_override('mechanism_drivers',
                                     ['logger', 'opendaylight'], 'ml2')
        config.cfg.CONF.set_override('url', 'http://127.0.0.1:9999', 'ml2_odl')
        config.cfg.CONF.set_override('username', 'someuser', 'ml2_odl')
        config.cfg.CONF.set_override('password', 'somepass', 'ml2_odl')
        self.mech = mech_driver.OpenDaylightMechanismDriver()
        self.mech.initialize()

    @staticmethod
    def _get_mock_network_operation_context():
        context = mock.Mock(current=FAKE_NETWORK.copy())
        return context

    @staticmethod
    def _get_mock_subnet_operation_context():
        context = mock.Mock(current=FAKE_SUBNET.copy())
        return context

    @staticmethod
    def _get_mock_port_operation_context():
        context = mock.Mock(current=FAKE_PORT.copy())
        context._plugin.get_security_group = mock.Mock(return_value={})
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
                cls._status_code_msgs[status_code], response=response)))
        return response

    def _test_single_operation(self, method, context, status_code,
                               exc_class=None, *args, **kwargs):
        self.mech.odl_drv.out_of_sync = False
        request_response = self._get_mock_request_response(status_code)
        with mock.patch('requests.request',
                        return_value=request_response) as mock_method:
            if exc_class is not None:
                self.assertRaises(exc_class, method, context)
            else:
                method(context)
        mock_method.assert_called_once_with(
            headers={'Content-Type': 'application/json'},
            auth=(config.cfg.CONF.ml2_odl.username,
                  config.cfg.CONF.ml2_odl.password),
            timeout=config.cfg.CONF.ml2_odl.timeout, *args, **kwargs)

    def _test_create_resource_postcommit(self, object_type, status_code,
                                         exc_class=None):
        method = getattr(self.mech, 'create_%s_postcommit' % object_type)
        context = self._get_mock_operation_context(object_type)
        url = '%s/%ss' % (config.cfg.CONF.ml2_odl.url, object_type)
        kwargs = {'url': url,
                  'data': DataMatcher('create', object_type, context)}
        self._test_single_operation(method, context, status_code, exc_class,
                                    'post', **kwargs)

    def _test_update_resource_postcommit(self, object_type, status_code,
                                         exc_class=None):
        method = getattr(self.mech, 'update_%s_postcommit' % object_type)
        context = self._get_mock_operation_context(object_type)
        url = '%s/%ss/%s' % (config.cfg.CONF.ml2_odl.url, object_type,
                             context.current['id'])
        kwargs = {'url': url,
                  'data': DataMatcher('update', object_type, context)}
        self._test_single_operation(method, context, status_code, exc_class,
                                    'put', **kwargs)

    def _test_delete_resource_postcommit(self, object_type, status_code,
                                         exc_class=None):
        method = getattr(self.mech, 'delete_%s_postcommit' % object_type)
        context = self._get_mock_operation_context(object_type)
        url = '%s/%ss/%s' % (config.cfg.CONF.ml2_odl.url, object_type,
                             context.current['id'])
        kwargs = {'url': url, 'data': None}
        self._test_single_operation(method, context, status_code, exc_class,
                                    'delete', **kwargs)

    def test_create_network_postcommit(self):
        self._test_create_resource_postcommit('network',
                                              requests.codes.created)
        for status_code in (requests.codes.bad_request,
                            requests.codes.unauthorized):
            self._test_create_resource_postcommit(
                'network', status_code, requests.exceptions.HTTPError)

    def test_create_subnet_postcommit(self):
        self._test_create_resource_postcommit('subnet', requests.codes.created)
        for status_code in (requests.codes.bad_request,
                            requests.codes.unauthorized,
                            requests.codes.forbidden,
                            requests.codes.not_found,
                            requests.codes.conflict,
                            requests.codes.not_implemented):
            self._test_create_resource_postcommit(
                'subnet', status_code, requests.exceptions.HTTPError)

    def test_create_port_postcommit(self):
        self._test_create_resource_postcommit('port', requests.codes.created)
        for status_code in (requests.codes.bad_request,
                            requests.codes.unauthorized,
                            requests.codes.forbidden,
                            requests.codes.not_found,
                            requests.codes.conflict,
                            requests.codes.not_implemented,
                            requests.codes.service_unavailable):
            self._test_create_resource_postcommit(
                'port', status_code, requests.exceptions.HTTPError)

    def test_update_network_postcommit(self):
        self._test_update_resource_postcommit('network', requests.codes.ok)
        for status_code in (requests.codes.bad_request,
                            requests.codes.forbidden,
                            requests.codes.not_found):
            self._test_update_resource_postcommit(
                'network', status_code, requests.exceptions.HTTPError)

    def test_update_subnet_postcommit(self):
        self._test_update_resource_postcommit('subnet', requests.codes.ok)
        for status_code in (requests.codes.bad_request,
                            requests.codes.unauthorized,
                            requests.codes.forbidden,
                            requests.codes.not_found,
                            requests.codes.not_implemented):
            self._test_update_resource_postcommit(
                'subnet', status_code, requests.exceptions.HTTPError)

    def test_update_port_postcommit(self):
        self._test_update_resource_postcommit('port', requests.codes.ok)
        for status_code in (requests.codes.bad_request,
                            requests.codes.unauthorized,
                            requests.codes.forbidden,
                            requests.codes.not_found,
                            requests.codes.conflict,
                            requests.codes.not_implemented):
            self._test_update_resource_postcommit(
                'port', status_code, requests.exceptions.HTTPError)

    def test_delete_network_postcommit(self):
        self._test_delete_resource_postcommit('network',
                                              requests.codes.no_content)
        self._test_delete_resource_postcommit('network',
                                              requests.codes.not_found)
        for status_code in (requests.codes.unauthorized,
                            requests.codes.conflict):
            self._test_delete_resource_postcommit(
                'network', status_code, requests.exceptions.HTTPError)

    def test_delete_subnet_postcommit(self):
        self._test_delete_resource_postcommit('subnet',
                                              requests.codes.no_content)
        self._test_delete_resource_postcommit('subnet',
                                              requests.codes.not_found)
        for status_code in (requests.codes.unauthorized,
                            requests.codes.conflict,
                            requests.codes.not_implemented):
            self._test_delete_resource_postcommit(
                'subnet', status_code, requests.exceptions.HTTPError)

    def test_delete_port_postcommit(self):
        self._test_delete_resource_postcommit('port',
                                              requests.codes.no_content)
        self._test_delete_resource_postcommit('port',
                                              requests.codes.not_found)
        for status_code in (requests.codes.unauthorized,
                            requests.codes.forbidden,
                            requests.codes.not_implemented):
            self._test_delete_resource_postcommit(
                'port', status_code, requests.exceptions.HTTPError)

    def test_port_emtpy_tenant_id_work_around(self):
        """Validate the work around code of port creation"""
        plugin = mock.Mock()
        plugin_context = mock.Mock()
        network = self._get_mock_operation_context('network').current
        port = self._get_mock_operation_context('port').current
        tenant_id = network['tenant_id']
        port['tenant_id'] = ''

        with mock.patch.object(driver_context.db, 'get_network_segments'):
            context = driver_context.PortContext(
                plugin, plugin_context, port, network, {}, 0, None)
            self.mech.odl_drv.FILTER_MAP[
                odl_const.ODL_PORTS].filter_create_attributes(port, context)
            self.assertEqual(tenant_id, port['tenant_id'])

    def test_update_port_filter(self):
        """Validate the filter code on update port operation"""
        items_to_filter = ['network_id', 'id', 'status', 'tenant_id']
        plugin_context = mock.Mock()
        network = self._get_mock_operation_context('network').current
        subnet = self._get_mock_operation_context('subnet').current
        port = self._get_mock_operation_context('port').current
        port['fixed_ips'] = [{'subnet_id': subnet['id'],
                              'ip_address': '10.0.0.10'}]
        port['mac_address'] = port['mac_address'].upper()
        orig_port = copy.deepcopy(port)

        with mock.patch.object(driver_context.db, 'get_network_segments'):
            context = driver_context.PortContext(
                plugin, plugin_context, port, network, {}, 0, None)
            self.mech.odl_drv.FILTER_MAP[
                odl_const.ODL_PORTS].filter_update_attributes(port, context)
            for key, value in port.items():
                if key not in items_to_filter:
                    self.assertEqual(orig_port[key], value)


class TestOpenDaylightMechanismDriver(base.DietTestCase):

    # given valid  and invalid segments
    valid_segment = {
        api.ID: 'API_ID',
        api.NETWORK_TYPE: constants.TYPE_LOCAL,
        api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    invalid_segment = {
        api.ID: 'API_ID',
        api.NETWORK_TYPE: constants.TYPE_NONE,
        api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    def test_bind_port_front_end(self):
        given_front_end = mech_driver.OpenDaylightMechanismDriver()
        given_port_context = self.given_port_context()
        given_back_end = mech_driver.OpenDaylightDriver()
        given_front_end.odl_drv = given_back_end
        given_back_end.port_binding_controller = \
            legacy_port_binding.LegacyPortBindingManager()

        # when port is bound
        given_front_end.bind_port(given_port_context)

        # then context binding is setup with returned vif_type and valid
        # segment API ID
        given_port_context.set_binding.assert_called_once_with(
            self.valid_segment[api.ID], portbindings.VIF_TYPE_OVS,
            given_back_end.port_binding_controller.vif_details,
            status=n_constants.PORT_STATUS_ACTIVE)

    def given_port_context(self):
        from neutron.plugins.ml2 import driver_context as ctx

        # given NetworkContext
        network = mock.MagicMock(spec=api.NetworkContext)

        # given port context
        return mock.MagicMock(
            spec=ctx.PortContext, current={'id': 'CURRENT_CONTEXT_ID'},
            segments_to_bind=[self.valid_segment, self.invalid_segment],
            network=network,
            _new_bound_segment=self.valid_segment)
