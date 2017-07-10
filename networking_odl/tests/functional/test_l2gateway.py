#
# Copyright (C) 2017 Ericsson India Global Services Pvt Ltd.
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

import contextlib
import copy

import mock
import webob.exc

from neutron.api import extensions as api_extensions
from neutron.db import servicetype_db as sdb
from neutron.tests.unit.plugins.ml2 import test_plugin
from oslo_utils import uuidutils

from networking_l2gw import extensions as l2gw_extensions
from networking_l2gw.services.l2gateway.common import constants as l2gw_const
from networking_l2gw.services.l2gateway.plugin import L2GatewayPlugin
from networking_odl.common import constants as odl_const
from networking_odl.tests.functional import base

_uuid = uuidutils.generate_uuid


class L2GatewayTestCaseMixin(object):

    devices = [{'device_name': 's1',
                'interfaces': [{'name': 'int1'}]
                },
               {'device_name': 's2',
                'interfaces': [{'name': 'int2', 'segmentation_id': [10, 20]}]
                }]
    l2gw_data = {l2gw_const.GATEWAY_RESOURCE_NAME: {'tenant_id': _uuid(),
                                                    'name': 'l2gw',
                                                    'devices': devices}}

    def setUp(self):
        """Perform parent setup with the common plugin configuration class."""
        # Ensure that the parent setup can be called without arguments
        # by the common configuration setUp.
        bits = self.service_provider.split(':')
        provider = {
            'service_type': bits[0],
            'name': bits[1],
            'driver': bits[2],
            'default': True
        }

        # override the default service provider
        self.service_providers = (
            mock.patch.object(sdb.ServiceTypeManager,
                              'get_service_providers').start())
        self.service_providers.return_value = [provider]
        super(L2GatewayTestCaseMixin, self).setUp()

    @contextlib.contextmanager
    def l2gateway(self, do_delete=True, **kwargs):
        req_data = copy.deepcopy(self.l2gw_data)

        fmt = 'json'
        if kwargs.get('data'):
            req_data = kwargs.get('data')
        else:
            req_data[l2gw_const.GATEWAY_RESOURCE_NAME].update(kwargs)
        l2gw_req = self.new_create_request(l2gw_const.L2_GATEWAYS,
                                           req_data, fmt=fmt)
        res = l2gw_req.get_response(self.ext_api)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        l2gw = self.deserialize('json', res)
        yield l2gw
        if do_delete:
            self._delete(l2gw_const.L2_GATEWAYS,
                         l2gw[l2gw_const.GATEWAY_RESOURCE_NAME]['id'])

    @contextlib.contextmanager
    def l2gateway_connection(self, nw_id, l2gw_id,
                             do_delete=True, **kwargs):
        req_data = {
            l2gw_const.CONNECTION_RESOURCE_NAME:
                {'tenant_id': _uuid(),
                 'network_id': nw_id,
                 'l2_gateway_id': l2gw_id}
        }

        fmt = 'json'
        if kwargs.get('data'):
            req_data = kwargs.get('data')
        else:
            req_data[l2gw_const.CONNECTION_RESOURCE_NAME].update(kwargs)
        l2gw_connection_req = self.new_create_request(
            l2gw_const.L2_GATEWAYS_CONNECTION, req_data, fmt=fmt)
        res = l2gw_connection_req.get_response(self.ext_api)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        l2gw_connection = self.deserialize('json', res)
        yield l2gw_connection
        if do_delete:
            self._delete(l2gw_const.L2_GATEWAYS_CONNECTION,
                         l2gw_connection
                         [l2gw_const.CONNECTION_RESOURCE_NAME]['id'])

    @staticmethod
    def convert_to_odl_l2gw_connection(l2gw_connection_in):
        odl_l2_gw_conn_data = copy.deepcopy(
            l2gw_connection_in[l2gw_const.CONNECTION_RESOURCE_NAME])
        odl_l2_gw_conn_data['gateway_id'] = (
            odl_l2_gw_conn_data['l2_gateway_id'])
        odl_l2_gw_conn_data.pop('l2_gateway_id')
        return {odl_const.ODL_L2GATEWAY_CONNECTION: odl_l2_gw_conn_data}


class _TestL2GatewayBase(base.OdlTestsBase, L2GatewayTestCaseMixin):

    def get_ext_managers(self):
        extensions_path = ':'.join(l2gw_extensions.__path__)
        return api_extensions.PluginAwareExtensionManager(
            extensions_path,
            {'l2gw_plugin': L2GatewayPlugin()})

    def get_additional_service_plugins(self):
        l2gw_plugin_str = ('networking_l2gw.services.l2gateway.plugin.'
                           'L2GatewayPlugin')
        service_plugin = {'l2gw_plugin': l2gw_plugin_str}
        return service_plugin

    def test_l2gateway_create(self):
        with self.l2gateway(name='mygateway') as l2gateway:
            self.assert_resource_created(odl_const.ODL_L2GATEWAY, l2gateway)

    def test_l2gateway_update(self):
        with self.l2gateway(name='gateway1') as l2gateway:
            self.resource_update_test(odl_const.ODL_L2GATEWAY, l2gateway)

    def test_l2gateway_delete(self):
        with self.l2gateway(do_delete=False) as l2gateway:
            self.resource_delete_test(odl_const.ODL_L2GATEWAY, l2gateway)

    def test_l2gateway_connection_create_delete(self):
        odl_l2gw_connection = {}
        with self.network() as network:
            with self.l2gateway() as l2gateway:
                net_id = network['network']['id']
                l2gw_id = l2gateway[odl_const.ODL_L2GATEWAY]['id']
                with (self.l2gateway_connection(net_id, l2gw_id)
                      ) as l2gw_connection:
                    odl_l2gw_connection = (
                        self.convert_to_odl_l2gw_connection(l2gw_connection))
                    self.assert_resource_created(
                        odl_const.ODL_L2GATEWAY_CONNECTION,
                        odl_l2gw_connection)
                self.assertIsNone(self.get_odl_resource(
                    odl_const.ODL_L2GATEWAY_CONNECTION, odl_l2gw_connection))


class TestL2gatewayV1Driver(_TestL2GatewayBase,
                            test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight']
    service_provider = ('L2GW:OpenDaylight:networking_odl.l2gateway.driver.'
                        'OpenDaylightL2gwDriver:default')


class TestL2gatewayV2Driver(base.V2DriverAdjustment, _TestL2GatewayBase,
                            test_plugin.Ml2PluginV2TestCase):
    _mechanism_drivers = ['opendaylight_v2']
    service_provider = ('L2GW:OpenDaylight:networking_odl.l2gateway.driver_v2.'
                        'OpenDaylightL2gwDriver:default')
