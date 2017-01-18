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

from copy import deepcopy
import mock
from os import path as os_path
from string import Template

from neutron.plugins.common import constants
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2 import driver_context as ctx
from neutron_lib.api.definitions import portbindings
from neutron_lib import constants as n_const
from neutron_lib.plugins import directory

from networking_odl.ml2 import pseudo_agentdb_binding
from networking_odl.tests import base
from requests.exceptions import HTTPError

from neutron.tests.unit.db import test_db_base_plugin_v2 as test_plugin

AGENTDB_BINARY = 'neutron-odlagent-portbinding'
L2_TYPE = "ODL L2"


class TestPseudoAgentDBBindingController(base.DietTestCase):
    """Test class for AgentDBPortBinding."""

    # test data hostconfig and hostconfig-dbget
    sample_odl_hconfigs = {"hostconfigs": {"hostconfig": [
        {"host-id": "devstack",
         "host-type": "ODL L2",
         "config": """{"supported_vnic_types": [
                    {"vnic_type": "normal", "vif_type": "ovs",
                     "vif_details": {}}],
                    "allowed_network_types": [
                    "local", "vlan", "vxlan", "gre"],
                    "bridge_mappings": {"physnet1": "br-ex"}}"""}
    ]}}

    # Test data for string interpolation of substitutable identifers
    #   e.g. $PORT_ID identifier in the configurations JSON string  below shall
    # be substituted with portcontext.current['id'] eliminating the check
    # for specific vif_type making port-binding truly switch agnostic.
    # Refer: Python string templates and interpolation (string.Template)
    sample_hconf_str_tmpl_subs_vpp = {
        "host": "devstack",      # host-id in ODL JSON
        "agent_type": "ODL L2",  # host-type in ODL JSON
                                 # config in ODL JSON
        "configurations": {"supported_vnic_types": [
            {"vnic_type": "normal", "vif_type": "vhostuser",
             "vif_details": {
                 "uuid": "TEST_UUID",
                 "has_datapath_type_netdev": True,
                 "support_vhost_user": True,
                 "port_prefix": "socket_",
                 "vhostuser_socket_dir": "/tmp",
                 "vhostuser_ovs_plug": True,
                 "vhostuser_mode": "server",
                 "vhostuser_socket":
                     "/tmp/socket_$PORT_ID"
             }}],
            "allowed_network_types": [
                "local", "vlan", "vxlan", "gre"],
            "bridge_mappings": {"physnet1": "br-ex"}}
    }

    sample_hconf_str_tmpl_subs_ovs = {
        "host": "devstack",      # host-id in ODL JSON
        "agent_type": "ODL L2",  # host-type in ODL JSON
                                 # config in ODL JSON
        "configurations": {"supported_vnic_types": [
            {"vnic_type": "normal", "vif_type": "vhostuser",
             "vif_details": {
                 "uuid": "TEST_UUID",
                 "has_datapath_type_netdev": True,
                 "support_vhost_user": True,
                 "port_prefix": "vhu_",
                 "vhostuser_socket_dir": "/var/run/openvswitch",
                 "vhostuser_ovs_plug": True,
                 "vhostuser_mode": "client",
                 "vhostuser_socket":
                     "/var/run/openvswitch/vhu_$PORT_ID"
             }}],
            "allowed_network_types": [
                "local", "vlan", "vxlan", "gre"],
            "bridge_mappings": {"physnet1": "br-ex"}}
    }

    sample_hconf_str_tmpl_nosubs = {
        "host": "devstack",      # host-id in ODL JSON
        "agent_type": "ODL L2",  # host-type in ODL JSON
                                 # config in ODL JSON
        "configurations": {"supported_vnic_types": [
            {"vnic_type": "normal", "vif_type": "ovs",
             "vif_details": {
                 "uuid": "TEST_UUID",
                 "has_datapath_type_netdev": True,
                 "support_vhost_user": True,
                 "port_prefix": "socket_",
                 "vhostuser_socket_dir": "/tmp",
                 "vhostuser_ovs_plug": True,
                 "vhostuser_mode": "server",
                 "vhostuser_socket":
                     "/var/run/openvswitch/PORT_NOSUBS"
             }}],
            "allowed_network_types": [
                "local", "vlan", "vxlan", "gre"],
            "bridge_mappings": {"physnet1": "br-ex"}}
    }

    # Test data for vanilla OVS
    sample_hconfig_dbget_ovs = {"configurations": {"supported_vnic_types": [
        {"vnic_type": "normal", "vif_type": portbindings.VIF_TYPE_OVS,
         "vif_details": {
             "some_test_details": None
         }}],
        "allowed_network_types": ["local", "vlan", "vxlan", "gre"],
        "bridge_mappings": {"physnet1": "br-ex"}}}

    # Test data for OVS-DPDK
    sample_hconfig_dbget_ovs_dpdk = {"configurations": {
        "supported_vnic_types": [{
            "vnic_type": "normal",
            "vif_type": portbindings.VIF_TYPE_VHOST_USER,
            "vif_details": {
                "uuid": "TEST_UUID",
                "has_datapath_type_netdev": True,
                "support_vhost_user": True,
                "port_prefix": "vhu_",
                # Assumption: /var/run mounted as tmpfs
                "vhostuser_socket_dir": "/var/run/openvswitch",
                "vhostuser_ovs_plug": True,
                "vhostuser_mode": "client",
                "vhostuser_socket": "/var/run/openvswitch/vhu_$PORT_ID"}}],
        "allowed_network_types": ["local", "vlan", "vxlan", "gre"],
        "bridge_mappings": {"physnet1": "br-ex"}}}

    # Test data for VPP
    sample_hconfig_dbget_vpp = {"configurations": {"supported_vnic_types": [
        {"vnic_type": "normal", "vif_type": portbindings.VIF_TYPE_VHOST_USER,
         "vif_details": {
             "uuid": "TEST_UUID",
             "has_datapath_type_netdev": True,
             "support_vhost_user": True,
             "port_prefix": "socket_",
             "vhostuser_socket_dir": "/tmp",
             "vhostuser_ovs_plug": True,
             "vhostuser_mode": "server",
             "vhostuser_socket": "/tmp/socket_$PORT_ID"
         }}],
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
        self.useFixture(base.OpenDaylightRestClientFixture())

        fake_agents_db = mock.MagicMock()
        fake_agents_db.create_or_update_agent = mock.MagicMock()

        self.mgr = pseudo_agentdb_binding.PseudoAgentDBBindingController(
            db_plugin=fake_agents_db)

    def test_make_hostconf_uri(self):
        """test make uri."""
        test_path = '/restconf/neutron:neutron/hostconfigs'
        expected = "http://localhost:8080/restconf/neutron:neutron/hostconfigs"
        test_uri = self.mgr._make_hostconf_uri(path=test_path)

        self.assertEqual(expected, test_uri)

    def test_update_agents_db(self):
        """test agent update."""
        self.mgr._update_agents_db(
            hostconfigs=self.sample_odl_hconfigs['hostconfigs']['hostconfig'])
        self.mgr.agents_db.create_or_update_agent.assert_called_once()

    def _get_raised_response(self, json_data, status_code):

        class MockHTTPError(HTTPError):
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
                self.response = self

        class MockResponse(object):
            def __init__(self, json_data, status_code):
                self.raise_obj = MockHTTPError(json_data, status_code)

            def raise_for_status(self):
                raise self.raise_obj

        return MockResponse(json_data, status_code)

    def test_hostconfig_response_404(self):
        with mock.patch.object(self.mgr.odl_rest_client,
                               'get', return_value=self.
                               _get_raised_response({}, 404)):
                self.assertEqual(self.mgr._rest_get_hostconfigs(), [])

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

    def test_bind_port_with_vif_type_ovs(self):
        """test bind_port with vanilla ovs."""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment])

        vif_type = portbindings.VIF_TYPE_OVS
        vif_details = {'some_test_details': None}

        self.mgr._hconfig_bind_port(
            port_context, self.sample_hconfig_dbget_ovs)

        port_context.set_binding.assert_called_once_with(
            self.test_valid_segment[api.ID], vif_type,
            vif_details, status=n_const.PORT_STATUS_ACTIVE)

    def _set_pass_vif_details(self, port_context, vif_details):
        """extract vif_details and update vif_details if needed."""
        vhostuser_socket_dir = vif_details.get(
            'vhostuser_socket_dir', '/var/run/openvswitch')
        port_spec = vif_details.get(
            'port_prefix', 'vhu_') + port_context.current['id']
        socket_path = os_path.join(vhostuser_socket_dir, port_spec)
        vif_details.update({portbindings.VHOST_USER_SOCKET: socket_path})

        return vif_details

    def test_bind_port_with_vif_type_vhost_user(self):
        """test bind_port with ovs-dpdk."""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment],
            host_agents=[deepcopy(self.sample_hconf_str_tmpl_subs_ovs)])

        self.mgr.bind_port(port_context)

        pass_vif_type = portbindings.VIF_TYPE_VHOST_USER
        pass_vif_details = self.sample_hconfig_dbget_ovs_dpdk[
            'configurations']['supported_vnic_types'][0]['vif_details']
        self._set_pass_vif_details(port_context, pass_vif_details)

        port_context.set_binding.assert_called_once_with(
            self.test_valid_segment[api.ID], pass_vif_type,
            pass_vif_details, status=n_const.PORT_STATUS_ACTIVE)

    def test_bind_port_with_vif_type_vhost_user_vpp(self):
        """test bind_port with vpp."""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment],
            host_agents=[deepcopy(self.sample_hconf_str_tmpl_subs_vpp)])

        self.mgr.bind_port(port_context)

        pass_vif_type = portbindings.VIF_TYPE_VHOST_USER
        pass_vif_details = self.sample_hconfig_dbget_vpp['configurations'][
            'supported_vnic_types'][0]['vif_details']
        self._set_pass_vif_details(port_context, pass_vif_details)

        port_context.set_binding.assert_called_once_with(
            self.test_valid_segment[api.ID], pass_vif_type,
            pass_vif_details, status=n_const.PORT_STATUS_ACTIVE)

    def test_bind_port_without_valid_segment(self):
        """test bind_port without a valid segment."""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment])

        self.mgr._hconfig_bind_port(
            port_context, self.sample_hconfig_dbget_ovs)

        port_context.set_binding.assert_not_called()

    def test_no_str_template_substitution_in_configuration_string(self):
        """Test for no identifier substituion in config JSON string."""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment])

        hconf_dict = self.mgr._substitute_hconfig_tmpl(
            port_context, self.sample_hconf_str_tmpl_nosubs)

        test_string = hconf_dict['configurations'][
            'supported_vnic_types'][0][
                'vif_details'][portbindings.VHOST_USER_SOCKET]

        expected_str = '/var/run/openvswitch/PORT_NOSUBS'

        self.assertEqual(expected_str, test_string)

    def test_str_template_substitution_in_configuration_string(self):
        """Test for identifier substitution in config JSON string."""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment])

        hconf_dict = self.mgr._substitute_hconfig_tmpl(
            port_context, self.sample_hconf_str_tmpl_subs_vpp)

        test_string = hconf_dict['configurations'][
            'supported_vnic_types'][0][
                'vif_details'][portbindings.VHOST_USER_SOCKET]

        expected_str = Template('/tmp/socket_$PORT_ID')
        expected_str = expected_str.safe_substitute({
            'PORT_ID': port_context.current['id']})

        self.assertEqual(expected_str, test_string)

    def _fake_port_context(self, fake_segments, host_agents=None):
        network = mock.MagicMock(spec=api.NetworkContext)
        return mock.MagicMock(
            spec=ctx.PortContext,
            current={'id': 'CONTEXT_ID',
                     portbindings.VNIC_TYPE: portbindings.VNIC_NORMAL},
            segments_to_bind=fake_segments, network=network,
            host_agents=lambda agent_type: host_agents)


class TestPseudoAgentDBBindingControllerBug1608659(
        test_plugin.NeutronDbPluginV2TestCase):
    """Test class for Bug1608659."""

    # test data hostconfig
    sample_odl_hconfigs = {"hostconfigs": {"hostconfig": [
        {"host-id": "devstack-control",
         "host-type": "ODL L2",
         "config": """{"supported_vnic_types": [
             {"vnic_type": "normal", "vif_type": "vhostuser",
              "vif_details":
                  {"port_filter": "False",
                   "vhostuser_socket": "/var/run/openvswitch"}}],
             "allowed_network_types": [
                 "local", "vlan", "vxlan", "gre"],
             "bridge_mappings": {"physnet1": "br-ex"}}"""},
        {"host-id": "devstack-control",
         "host-type": "ODL L3",
         "config": """{ "some_details": "dummy_details" }"""}
    ]}}

    def setUp(self):
        super(TestPseudoAgentDBBindingControllerBug1608659, self).setUp(
            plugin='ml2')
        self.useFixture(base.OpenDaylightRestClientFixture())
        self.core_plugin = directory.get_plugin()
        self.mgr = pseudo_agentdb_binding.PseudoAgentDBBindingController(
            self.core_plugin)

    def test_execute_no_exception(self):
        with mock.patch.object(pseudo_agentdb_binding, 'LOG') as mock_log:
            self.mgr._update_agents_db(
                self.sample_odl_hconfigs['hostconfigs']['hostconfig'])
            # Assert no exception happened
            self.assertFalse(mock_log.exception.called)
