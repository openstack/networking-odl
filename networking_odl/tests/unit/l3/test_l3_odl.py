# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
test_l3_odl
----------------------------------

Tests for the L3 service plugin for networking-odl.
"""
import copy

import mock

from neutron.extensions import l3
from neutron.tests.unit.api.v2 import test_base
from neutron.tests.unit.extensions import base as test_extensions_base
from neutron_lib.api.definitions import l3 as l3_apidef
from neutron_lib.api.definitions import l3_ext_gw_mode as l3egm_apidef
from neutron_lib.plugins import constants
from webob import exc

from networking_odl.tests import base as odl_base


_get_path = test_base._get_path


class Testodll3(test_extensions_base.ExtensionTestCase):

    fmt = 'json'

    def setUp(self):
        self.useFixture(odl_base.OpenDaylightFeaturesFixture())
        self.useFixture(odl_base.OpenDaylightRestClientFixture())
        self.useFixture(odl_base.OpenDaylightPseudoAgentPrePopulateFixture())
        super(Testodll3, self).setUp()
        self._setUpExtension(
            'networking_odl.l3.l3_odl.OpenDaylightL3RouterPlugin',
            constants.L3, l3_apidef.RESOURCE_ATTRIBUTE_MAP,
            l3.L3, '', allow_pagination=True, allow_sorting=True,
            supported_extension_aliases=[l3_apidef.ALIAS, l3egm_apidef.ALIAS],
            use_quota=True)
        # support ext-gw-mode after fixture used via _setUpExtension()
        l3.L3().update_attributes_map(l3egm_apidef.RESOURCE_ATTRIBUTE_MAP)

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
        return context

    @staticmethod
    def _get_router_test():
        router_id = "234237d4-1e7f-11e5-9bd7-080027328c3a"
        router = {'router': {'name': 'router1', 'admin_state_up': True,
                             'tenant_id': router_id,
                             'project_id': router_id,
                             'external_gateway_info': None}}
        return router_id, router

    @staticmethod
    def _get_floating_ip_test():
        floating_ip_id = "e4997650-6a83-4230-950a-8adab8e524b2"
        floating_ip = {
            "floatingip": {"fixed_ip_address": None,
                           "floating_ip_address": None,
                           "floating_network_id": None,
                           "id": floating_ip_id,
                           "router_id": "d23abc8d-2991-4a55-ba98-2aaea84cc72",
                           "port_id": None,
                           "status": None,
                           "tenant_id": "test-tenant"
                           }
        }
        return floating_ip_id, floating_ip

    @staticmethod
    def _get_port_test():
        port_id = "3a44f4e5-1694-493a-a1fb-393881c673a4"
        subnet_id = "a2f1f29d-571b-4533-907f-5803ab96ead1"
        port = {'id': port_id,
                'network_id': "84b126bb-f45e-4b2e-8202-7e5ce9e21fe7",
                'fixed_ips': [{'ip_address': '19.4.4.4',
                               'prefixlen': 24,
                               'subnet_id': subnet_id}],
                'subnets': [{'id': subnet_id,
                             'cidr': '19.4.4.0/24',
                             'gateway_ip': '19.4.4.1'}]}
        return port_id, port

    def test_create_router(self):
        router_id, router = self._get_router_test()

        return_value = copy.deepcopy(router['router'])
        return_value.update({'status': "ACTIVE", 'id': router_id})

        instance = self.plugin.return_value
        instance.create_router.return_value = return_value
        instance.get_routers_count.return_value = 0

        res = self.api.post(_get_path('routers', fmt=self.fmt),
                            self.serialize(router),
                            content_type='application/%s' % self.fmt)

        instance.create_router.assert_called_once_with(mock.ANY, router=router)
        self.assertEqual(exc.HTTPCreated.code, res.status_int)
        res = self.deserialize(res)
        self.assertIn('router', res)
        router = res['router']
        self.assertEqual(router_id, router['id'])
        self.assertEqual("ACTIVE", router['status'])
        self.assertEqual(True, router['admin_state_up'])

    def test_update_router(self):
        router_id, router = self._get_router_test()

        router_request_info = {'external_gateway_info': {
            "network_id": "3c5bcddd-6af9-4e6b-9c3e-c153e521cab8",
            "enable_snat": True}
        }
        return_value = copy.deepcopy(router['router'])
        return_value.update(router_request_info)
        return_value.update({'status': "ACTIVE", 'id': router_id})

        instance = self.plugin.return_value
        instance.update_router.return_value = return_value

        router_request = {'router': router_request_info}
        res = self.api.put(_get_path('routers', id=router_id, fmt=self.fmt),
                           self.serialize(router_request))
        instance.update_router.assert_called_once_with(mock.ANY, router_id,
                                                       router=router_request)

        self.assertEqual(exc.HTTPOk.code, res.status_int)
        res = self.deserialize(res)
        self.assertIn('router', res)
        router = res['router']
        self.assertEqual(router_id, router['id'])
        self.assertEqual("3c5bcddd-6af9-4e6b-9c3e-c153e521cab8",
                         router["external_gateway_info"]['network_id'])
        self.assertEqual(True, router["external_gateway_info"]['enable_snat'])

    def test_delete_router(self):
        router_id, router = self._get_router_test()

        instance = self.plugin.return_value

        res = self.api.delete(_get_path('routers', id=router_id, fmt=self.fmt))
        instance.delete_router.assert_called_once_with(mock.ANY, router_id)

        self.assertEqual(exc.HTTPNoContent.code, res.status_int)

    def test_create_floating_ip(self):
        floating_ip_id, floating_ip = self._get_floating_ip_test()
        port_id, port = self._get_port_test()

        floating_ip_request_info = {"floating_network_id":
                                    "376da547-b977-4cfe-9cba-275c80debf57",
                                    "tenant_id": "test-tenant",
                                    "project_id": "test-tenant",
                                    "fixed_ip_address": "10.0.0.3",
                                    "subnet_id": port['subnets'][0]['id'],
                                    "port_id": port_id,
                                    "floating_ip_address": "172.24.4.228"
                                    }

        return_value = copy.deepcopy(floating_ip['floatingip'])
        return_value.update(floating_ip_request_info)
        return_value.update({'status': "ACTIVE"})

        instance = self.plugin.return_value
        instance.create_floatingip.return_value = return_value
        instance.get_floatingips_count.return_value = 0
        instance.get_port = mock.Mock(return_value=port)

        floating_ip_request = {'floatingip': floating_ip_request_info}

        res = self.api.post(_get_path('floatingips', fmt=self.fmt),
                            self.serialize(floating_ip_request))

        instance.create_floatingip.\
            assert_called_once_with(mock.ANY,
                                    floatingip=floating_ip_request)

        self.assertEqual(exc.HTTPCreated.code, res.status_int)
        res = self.deserialize(res)
        self.assertIn('floatingip', res)
        floatingip = res['floatingip']
        self.assertEqual(floating_ip_id, floatingip['id'])
        self.assertEqual("ACTIVE", floatingip['status'])

    def test_update_floating_ip(self):
        floating_ip_id, floating_ip = self._get_floating_ip_test()

        floating_ip_request_info = {"port_id": None}

        return_value = copy.deepcopy(floating_ip['floatingip'])
        return_value.update(floating_ip_request_info)
        return_value.update({"status": "ACTIVE",
                             "tenant_id": "test-tenant",
                             "floating_network_id":
                                 "376da547-b977-4cfe-9cba-275c80debf57",
                             "fixed_ip_address": None,
                             "floating_ip_address": "172.24.4.228"
                             })

        instance = self.plugin.return_value
        instance.get_floatingip = mock.Mock(return_value=floating_ip)
        instance.update_floatingip.return_value = return_value
        port_id, port = self._get_port_test()
        instance.get_port = mock.Mock(return_value=port)

        floating_ip_request = {'floatingip': floating_ip_request_info}

        res = self.api.put(_get_path('floatingips', id=floating_ip_id,
                                     fmt=self.fmt),
                           self.serialize(floating_ip_request))

        instance.update_floatingip.\
            assert_called_once_with(mock.ANY,
                                    floating_ip_id,
                                    floatingip=floating_ip_request)

        self.assertEqual(exc.HTTPOk.code, res.status_int)
        res = self.deserialize(res)
        self.assertIn('floatingip', res)
        floatingip = res['floatingip']
        self.assertEqual(floating_ip_id, floatingip['id'])
        self.assertIsNone(floatingip['port_id'])
        self.assertIsNone(floatingip['fixed_ip_address'])

    def test_delete_floating_ip(self):
        floating_ip_id, floating_ip = self._get_floating_ip_test()

        instance = self.plugin.return_value
        instance.get_floatingip = mock.Mock(return_value=floating_ip)
        res = self.api.delete(_get_path('floatingips', id=floating_ip_id))
        instance.delete_floatingip.assert_called_once_with(mock.ANY,
                                                           floating_ip_id)

        self.assertEqual(exc.HTTPNoContent.code, res.status_int)

    def test_add_router_interface(self):
        router_id, router = self._get_router_test()
        interface_info = {"subnet_id": "a2f1f29d-571b-4533-907f-5803ab96ead1"}
        return_value = {"tenant_id": "6ba032e4730d42e2ad928f430f5da33e",
                        "port_id": "3a44f4e5-1694-493a-a1fb-393881c673a4",
                        "id": router_id
                        }
        return_value.update(interface_info)

        instance = self.plugin.return_value
        instance.add_router_interface.return_value = return_value

        res = self.api.put(_get_path('routers', id=router_id,
                                     action="add_router_interface",
                                     fmt=self.fmt),
                           self.serialize(interface_info)
                           )

        instance.add_router_interface.assert_called_once_with(mock.ANY,
                                                              router_id,
                                                              interface_info)

        self.assertEqual(exc.HTTPOk.code, res.status_int)
        res = self.deserialize(res)
        self.assertEqual(router_id, res['id'])
        self.assertEqual("a2f1f29d-571b-4533-907f-5803ab96ead1",
                         res['subnet_id'])

    def test_remove_router_interface(self):
        router_id, router = self._get_router_test()
        interface_info = {"subnet_id": "a2f1f29d-571b-4533-907f-5803ab96ead1",
                          "port_id": "3a44f4e5-1694-493a-a1fb-393881c673a4"
                          }
        return_value = {"tenant_id": "6ba032e4730d42e2ad928f430f5da33e",
                        "id": router_id
                        }
        return_value.update(interface_info)

        instance = self.plugin.return_value
        instance.remove_router_interface.return_value = return_value
        res = self.api.put(_get_path('routers', id=router_id,
                                     action="remove_router_interface",
                                     fmt=self.fmt),
                           self.serialize(interface_info)
                           )

        instance.remove_router_interface.\
            assert_called_once_with(mock.ANY,
                                    router_id,
                                    interface_info)

        self.assertEqual(exc.HTTPOk.code, res.status_int)
        res = self.deserialize(res)
        self.assertEqual(router_id, res['id'])
        self.assertEqual("a2f1f29d-571b-4533-907f-5803ab96ead1",
                         res['subnet_id'])
