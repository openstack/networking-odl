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

import mock

from neutron.common import constants as n_const
from neutron.extensions import portbindings
from neutron.plugins.common import constants
from neutron.plugins.ml2 import config
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2 import driver_context as ctx

from networking_odl.ml2 import pseudo_agentdb_binding
from networking_odl.tests import base

AGENTDB_BINARY = 'neutron-odlagent-portbinding'
L2_TYPE = "ODL L2"


class TestPseudoAgentDBBindingController(base.DietTestCase):
    """Test class for AgentDBPortBinding."""

    # test data hostconfig and hostconfig-dbget
    test_odl_hconfigs = {"hostconfigs": {"hostconfig": [
        {"host-id": "devstack",
         "host-type": "ODL L2",
         "config": """{"supported_vnic_types": [
                    {"vnic_type": "normal", "vif_type": "ovs",
                     "vif_details": {}}],
                    "allowed_network_types": [
                    "local", "vlan", "vxlan", "gre"],
                    "bridge_mappings": {"physnet1": "br-ex"}}"""}
    ]}}

    test_hconfig_dbget = {"configurations": {"supported_vnic_types": [
        {"vnic_type": "normal", "vif_type": "ovs", "vif_details": {}}],
        "allowed_network_types": ["local", "vlan", "vxlan", "gre"],
        "bridge_mappings": {"physnet1": "br-ex"}}}

    # test data valid  and invalid segments
    test_valid_segment = {
        api.ID: 'API_ID',
        api.NETWORK_TYPE: constants.TYPE_LOCAL,
        api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    test_invalid_segment = {
        api.ID: 'API_ID',
        api.NETWORK_TYPE: constants.TYPE_NONE,
        api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    def setUp(self):
        """Setup test."""
        super(TestPseudoAgentDBBindingController, self).setUp()

        config.cfg.CONF.set_override('url',
                                     'http://localhost:8181'
                                     '/controller/nb/v2/neutron', 'ml2_odl')
        self.mgr = pseudo_agentdb_binding.PseudoAgentDBBindingController()

    def test_make_hostconf_uri(self):
        """test make uri."""
        TEST_PATH = "/restconf/hostconfigs"
        TEST_URI = "http://localhost:8080" + TEST_PATH
        uri = self.mgr._make_hostconf_uri(path=TEST_PATH)
        self.assertEqual(uri, TEST_URI)

    def test_update_agents_db(self):
        """test agent update."""
        agent_db = mock.MagicMock()
        self.mgr._update_agents_db(agent_db, self.test_odl_hconfigs[
            'hostconfigs']['hostconfig'])
        agent_db.create_or_update_agent.assert_called_once()

    def test_is_valid_segment(self):
        """Validate the _check_segment method."""
        all_network_types = [constants.TYPE_FLAT, constants.TYPE_GRE,
                             constants.TYPE_LOCAL, constants.TYPE_VXLAN,
                             constants.TYPE_VLAN, constants.TYPE_NONE]

        valid_types = {
            network_type
            for network_type in all_network_types
            if self.mgr._is_valid_segment({api.NETWORK_TYPE: network_type}, {
                'allowed_network_types': [
                    constants.TYPE_LOCAL, constants.TYPE_GRE,
                    constants.TYPE_VXLAN, constants.TYPE_VLAN]})}

        self.assertEqual({
            constants.TYPE_LOCAL, constants.TYPE_GRE, constants.TYPE_VXLAN,
            constants.TYPE_VLAN}, valid_types)

    def test_hconfig_bind_port(self):
        """test bind_port."""
        network = mock.MagicMock(spec=api.NetworkContext)

        port_context = mock.MagicMock(
            spec=ctx.PortContext,
            current={'id': 'CURRENT_CONTEXT_ID',
                     portbindings.VNIC_TYPE: portbindings.VNIC_NORMAL},
            segments_to_bind=[self.test_valid_segment,
                              self.test_invalid_segment], network=network)

        vif_type = portbindings.VIF_TYPE_OVS
        vif_details = {}

        self.mgr._hconfig_bind_port(port_context, self.test_hconfig_dbget)

        port_context.set_binding.assert_called_once_with(
            self.test_valid_segment[api.ID], vif_type,
            vif_details, status=n_const.PORT_STATUS_ACTIVE)
