# Copyright (C) 2016 Intel Corp. Isaku Yamahata <isaku.yamahata@gmail com>
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
from neutron.tests import base
from neutron_lib import constants as n_const

from networking_odl.common import filters


PROFILE = {"capabilities": ["switchdev"]}
PROFILE_STR = '{"capabilities": ["switchdev"]}'
FAKE_PORT = {'status': 'DOWN',
             'binding:host_id': '',
             'allowed_address_pairs': [],
             'device_owner': 'fake_owner',
             'binding:profile': {"capabilities": ["switchdev"]},
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


class TestFilters(base.DietTestCase):

    def _check_id(self, resource, project_id):
        filters._populate_project_id_and_tenant_id(resource)
        self.assertIn(resource['project_id'], project_id)
        self.assertIn(resource['tenant_id'], project_id)

    def _test_populate_project_id_and_tenant_id(self, project_id):
        self._check_id({'project_id': project_id}, project_id)
        self._check_id({'tenant_id': project_id}, project_id)
        self._check_id({'project_id': project_id,
                        'tenant_id': project_id}, project_id)

    def test_populate_project_id_and_tenant_id_with_id(self):
        self._test_populate_project_id_and_tenant_id(
            '01234567-890a-bcde-f012-3456789abcde')
        self._test_populate_project_id_and_tenant_id("")

    def test_populate_project_id_and_tenant_id_without_id(self):
        resource = {}
        filters._populate_project_id_and_tenant_id(resource)
        self.assertNotIn('project_id', resource)
        self.assertNotIn('tenant_id', resource)

    def test_populate_project_id_and_tenant_id_with_router(self):
        # test case for OpenDaylightL3RouterPlugin.delete_router()
        # it passes data as dependency_list as list, not dict
        resource0 = ['gw_port_id']
        resource1 = resource0[:]
        filters._populate_project_id_and_tenant_id(resource1)
        self.assertEqual(resource0, resource1)

    def test_populate_project_id_and_tenant_id_with_floatingip(self):
        # test case for OpenDaylightL3RouterPlugin.delete_floatingip()
        # it passes data as dependency_list as list, not dict.
        resource0 = ['router_uuid', 'floatingip_uuid']
        resource1 = resource0[:]
        filters._populate_project_id_and_tenant_id(resource1)
        self.assertEqual(resource0, resource1)

    def test_sgrule_scrub_unknown_protocol_name(self):
        KNOWN_PROTO_NAMES = (n_const.PROTO_NAME_TCP,
                             n_const.PROTO_NAME_UDP,
                             n_const.PROTO_NAME_ICMP,
                             n_const.PROTO_NAME_IPV6_ICMP_LEGACY)
        for protocol_name in KNOWN_PROTO_NAMES:
            self.assertEqual(
                protocol_name,
                filters._sgrule_scrub_unknown_protocol_name(protocol_name))

        self.assertEqual(
            n_const.PROTO_NUM_AH,
            filters._sgrule_scrub_unknown_protocol_name(n_const.PROTO_NAME_AH))
        self.assertEqual("1", filters._sgrule_scrub_unknown_protocol_name("1"))

    def test_sgrule_scrub_icmpv6_name(self):
        for protocol_name in (n_const.PROTO_NAME_ICMP,
                              n_const.PROTO_NAME_IPV6_ICMP,
                              n_const.PROTO_NAME_IPV6_ICMP_LEGACY):
            sgrule = {'ethertype': n_const.IPv6,
                      'protocol': protocol_name}
            filters._sgrule_scrub_icmpv6_name(sgrule)
            self.assertEqual(n_const.PROTO_NAME_IPV6_ICMP_LEGACY,
                             sgrule['protocol'])

    def test_convert_value_to_string(self):
        port = {"binding:profile": PROFILE,
                "other_param": ["some", "values"]}
        filters._convert_value_to_str(port, 'binding:profile')
        self.assertIs(type(port['binding:profile']), str)
        self.assertEqual(port['binding:profile'], PROFILE_STR)
        self.assertIsNot(type(port['other_param']), str)

    def test_convert_value_to_string_unicode(self):
        port = {"binding:profile": {u"capabilities": [u"switchdev"]}}
        filters._convert_value_to_str(port, "binding:profile")
        self.assertEqual(port["binding:profile"], PROFILE_STR)

    def test_convert_value_to_string_missing_key_is_logged(self):
        port = {}
        with mock.patch.object(filters, 'LOG') as mock_log:
            filters._convert_value_to_str(port, 'invalid_key')
            mock_log.warning.assert_called_once_with(
                "key %s is not present in dict %s", 'invalid_key', port)

    def _filter_port_func_binding_profile_to_string(self, func):
        port = copy.deepcopy(FAKE_PORT)
        func(port)
        self.assertEqual(port["binding:profile"], PROFILE_STR)

    def test_filter_port_create_binding_profile_string(self):
        self._filter_port_func_binding_profile_to_string(
            filters._filter_port_create)

    def test_filter_port_update_binding_profile_string(self):
        self._filter_port_func_binding_profile_to_string(
            filters._filter_port_update)
