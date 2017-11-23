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

from neutron.tests import base
from oslo_config import fixture as config_fixture

from networking_odl.common import constants as odl_const
from networking_odl.common import utils


class TestUtils(base.DietTestCase):

    def setUp(self):
        self.cfg = self.useFixture(config_fixture.Config())
        super(TestUtils, self).setUp()

    # TODO(manjeets) remove this test once neutronify is
    # consolidated with make_plural
    def test_neutronify(self):
        self.assertEqual('a-b-c', utils.neutronify('a_b_c'))

    def test_neutronify_empty(self):
        self.assertEqual('', utils.neutronify(''))

    @staticmethod
    def _get_resources():
        # TODO(rajivk): Load balancer resources are not specified because
        # urls builder is registered explictly. Add load balancer resources
        # here, once lbaas url creation is directed through this method
        return {odl_const.ODL_SG: 'security-groups',
                odl_const.ODL_SG_RULE: 'security-group-rules',
                odl_const.ODL_NETWORK: 'networks',
                odl_const.ODL_SUBNET: 'subnets',
                odl_const.ODL_ROUTER: 'routers',
                odl_const.ODL_PORT: 'ports',
                odl_const.ODL_FLOATINGIP: 'floatingips',
                odl_const.ODL_QOS_POLICY: 'qos/policies',
                odl_const.ODL_TRUNK: 'trunks',
                odl_const.ODL_BGPVPN: 'bgpvpns',
                odl_const.ODL_SFC_FLOW_CLASSIFIER: 'sfc/flowclassifiers',
                odl_const.ODL_SFC_PORT_PAIR: 'sfc/portpairs',
                odl_const.ODL_SFC_PORT_PAIR_GROUP: 'sfc/portpairgroups',
                odl_const.ODL_SFC_PORT_CHAIN: 'sfc/portchains',
                odl_const.ODL_L2GATEWAY: 'l2-gateways',
                odl_const.ODL_L2GATEWAY_CONNECTION: 'l2gateway-connections'}

    def test_all_resources_url(self):
        for obj, url in self._get_resources().items():
            self.assertEqual(utils.make_url_object(obj), url)

    def test_get_odl_url(self):
        """test make uri."""
        self.cfg.config(url='http://localhost:8080/controller/nb/v2/neutron',
                        group='ml2_odl')
        test_path = '/restconf/neutron:neutron/hostconfigs'
        expected = "http://localhost:8080/restconf/neutron:neutron/hostconfigs"
        test_uri = utils.get_odl_url(path=test_path)

        self.assertEqual(expected, test_uri)
