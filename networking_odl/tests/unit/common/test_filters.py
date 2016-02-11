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

from neutron.tests import base
from neutron_lib import constants as n_const

from networking_odl.common import filters


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
