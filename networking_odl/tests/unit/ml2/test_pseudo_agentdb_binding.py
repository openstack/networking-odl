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
from os import path as os_path
from string import Template

import fixtures
import mock
from oslo_serialization import jsonutils
from requests.exceptions import HTTPError

from neutron.db import provisioning_blocks
from neutron.plugins.ml2 import driver_context as ctx
from neutron.plugins.ml2 import plugin as ml2_plugin
from neutron.tests.unit.db import test_db_base_plugin_v2 as test_plugin
from neutron.tests.unit import testlib_api
from neutron_lib.api.definitions import portbindings
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib import constants as n_const
from neutron_lib import fixture
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from neutron_lib.plugins.ml2 import api
from oslo_config import fixture as config_fixture

from networking_odl.common import odl_features
from networking_odl.common import websocket_client
from networking_odl.journal import periodic_task
from networking_odl.ml2 import pseudo_agentdb_binding
from networking_odl.tests import base


AGENTDB_BINARY = 'neutron-odlagent-portbinding'
L2_TYPE = "ODL L2"
# test data hostconfig and hostconfig-dbget
SAMPLE_ODL_HCONFIGS = {"hostconfigs": {"hostconfig": [
    {"host-id": "devstack",
     "host-type": "ODL L2",
     "config": """{"supported_vnic_types": [
                {"vnic_type": "normal", "vif_type": "ovs",
                 "vif_details": {}}],
                "allowed_network_types": [
                "local", "vlan", "vxlan", "gre"],
                "bridge_mappings": {"physnet1": "br-ex"}}"""}
]}}


class OpenDaylightAgentDBFixture(fixtures.Fixture):
    def _setUp(self):
        super(OpenDaylightAgentDBFixture, self)._setUp()
        fake_agents_db = mock.MagicMock()
        fake_agents_db.create_or_update_agent = mock.MagicMock()
        self.useFixture(fixture.PluginDirectoryFixture())
        directory.add_plugin(plugin_constants.CORE, fake_agents_db)


class TestPseudoAgentDBBindingTaskBase(base.DietTestCase):
    """Test class for AgentDBPortBindingTaskBase."""

    def setUp(self):
        """Setup test."""
        self.useFixture(base.OpenDaylightRestClientFixture())
        self.useFixture(base.OpenDaylightPseudoAgentPrePopulateFixture())
        self.useFixture(OpenDaylightAgentDBFixture())
        super(TestPseudoAgentDBBindingTaskBase, self).setUp()

        self.worker = pseudo_agentdb_binding.PseudoAgentDBBindingWorker()
        self.task = pseudo_agentdb_binding.PseudoAgentDBBindingTaskBase(
            self.worker)

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
        with mock.patch.object(self.task.odl_rest_client,
                               'get', return_value=self.
                               _get_raised_response({}, 404)):
                self.assertEqual(self.task._rest_get_hostconfigs(), [])


class TestPseudoAgentDBBindingPrePopulate(base.DietTestCase):
    KNOWN_HOST = 'known_host'
    AGENT_TYPE = pseudo_agentdb_binding.PseudoAgentDBBindingWorker.L2_TYPE

    def setUp(self):
        self.useFixture(base.OpenDaylightRestClientFixture())
        self.useFixture(OpenDaylightAgentDBFixture())
        super(TestPseudoAgentDBBindingPrePopulate, self).setUp()
        self.useFixture(fixture.CallbackRegistryFixture())

        self.ml2_plugin = mock.Mock()
        self.ml2_plugin.get_agents = mock.Mock(return_value=[])
        self.worker = mock.Mock()
        self.worker.known_agent = mock.Mock(return_value=False)
        self.worker.add_known_agent = mock.Mock()
        self.worker.update_agetns_db_row = mock.Mock()
        self.prepopulate = (pseudo_agentdb_binding.
                            PseudoAgentDBBindingPrePopulate(self.worker))

    def _call_before_port_binding(self, host):
        kwargs = {
            'context': mock.Mock(),
            'port': {
                portbindings.HOST_ID: host
            }
        }
        registry.notify(resources.PORT, events.BEFORE_CREATE, self.ml2_plugin,
                        **kwargs)

    def test_unspecified(self):
        self._call_before_port_binding(n_const.ATTR_NOT_SPECIFIED)
        self.worker.known_agent.assert_not_called()

    def test_empty_host(self):
        self._call_before_port_binding('')
        self.worker.known_agent.assert_not_called()

    def test_known_agent(self):
        self.worker.known_agent = mock.Mock(return_value=True)
        self._call_before_port_binding(self.KNOWN_HOST)
        self.worker.known_agent.assert_called()
        self.ml2_plugin.get_agents.assert_not_called()

    def test_agentdb_alive(self):
        self.ml2_plugin.get_agents = mock.Mock(return_value=[
            {'host': self.KNOWN_HOST,
             'agent_type': self.AGENT_TYPE,
             'alive': True}])
        self._call_before_port_binding(self.KNOWN_HOST)
        self.worker.known_agent.assert_called()
        self.ml2_plugin.get_agents.assert_called()
        self.worker.add_known_agents.assert_called_with([
            {'host': self.KNOWN_HOST,
             'agent_type': self.AGENT_TYPE,
             'alive': True}])
        self.worker.update_agents_db_row.assert_not_called()

    def test_agentdb_dead(self):
        self.ml2_plugin.get_agents = mock.Mock(return_value=[
            {'host': self.KNOWN_HOST,
             'agent_type': self.AGENT_TYPE,
             'alive': False}])
        self._call_before_port_binding(self.KNOWN_HOST)
        self.worker.known_agent.assert_called()
        self.ml2_plugin.get_agents.assert_called()
        self.worker.add_known_agents.assert_not_called()

    def test_unkown_hostconfig(self):
        with mock.patch.object(self.prepopulate,
                               'odl_rest_client') as mock_rest_client:
            mock_response = mock.Mock()
            mock_response.json = mock.Mock(
                return_value=SAMPLE_ODL_HCONFIGS['hostconfigs'])
            mock_rest_client.get = mock.Mock(return_value=mock_response)
            self._call_before_port_binding(self.KNOWN_HOST)
            self.worker.known_agent.assert_called()
            self.ml2_plugin.get_agents.assert_called()
            self.worker.add_known_agent.assert_not_called()
            self.worker.update_agents_db_row.assert_called_once()

    def test_http_error(self):
        with mock.patch.object(self.prepopulate,
                               'odl_rest_client') as mock_rest_client:
            mock_rest_client.get = mock.Mock(side_effect=Exception('error'))
            self._call_before_port_binding(self.KNOWN_HOST)
            self.worker.known_agent.assert_called()
            self.ml2_plugin.get_agents.assert_called()
            self.worker.add_known_agent.assert_not_called()
            self.worker.update_agents_db_row.assert_not_called()


class TestPseudoAgentDBBindingWorker(base.DietTestCase):
    """Test class for AgentDBPortBinding."""

    def setUp(self):
        """Setup test."""
        self.useFixture(base.OpenDaylightRestClientFixture())
        self.useFixture(base.OpenDaylightPseudoAgentPrePopulateFixture())
        self.useFixture(OpenDaylightAgentDBFixture())
        super(TestPseudoAgentDBBindingWorker, self).setUp()

        self.worker = pseudo_agentdb_binding.PseudoAgentDBBindingWorker()

    def test_update_agents_db(self):
        """test agent update."""
        self.worker.update_agents_db(
            hostconfigs=SAMPLE_ODL_HCONFIGS['hostconfigs']['hostconfig'])
        self.worker.agents_db.create_or_update_agent.assert_called_once()


class TestPseudoAgentDBBindingController(base.DietTestCase):
    """Test class for AgentDBPortBinding."""

    # Test data for string interpolation of substitutable identifers
    #   e.g. $PORT_ID identifier in the configurations JSON string  below shall
    # be substituted with portcontext.current['id'] eliminating the check
    # for specific vif_type making port-binding truly switch agnostic.
    # Refer: Python string templates and interpolation (string.Template)
    sample_hconf_str_tmpl_subs_vpp = {
        "host": "devstack",      # host-id in ODL JSON
        "agent_type": "ODL L2",  # host-type in ODL JSON
                                 # config in ODL JSON
        "alive": True,
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
        "alive": True,
        "configurations": {"supported_vnic_types": [
            {"vnic_type": "normal", "vif_type": "vhostuser",
             "vif_details": {
                 "uuid": "TEST_UUID",
                 "has_datapath_type_netdev": True,
                 "support_vhost_user": True,
                 "port_prefix": "vhu",
                 "vhostuser_socket_dir": "/var/run/openvswitch",
                 "vhostuser_ovs_plug": True,
                 "vhostuser_mode": "client",
                 "vhostuser_socket":
                     "/var/run/openvswitch/vhu$PORT_ID"
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

    # Test data for vanilla OVS with SR-IOV offload
    sample_hconfig_dbget_ovs_sriov_offload = {"configurations": {
        "supported_vnic_types": [{
            "vnic_type": "normal",
            "vif_type": portbindings.VIF_TYPE_OVS,
            "vif_details": {
                "some_test_details": None}}, {
            "vnic_type": "direct",
            "vif_type": portbindings.VIF_TYPE_OVS,
            "vif_details": {
                "some_test_details": None
            }}, ],
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
                "port_prefix": "vhu",
                # Assumption: /var/run mounted as tmpfs
                "vhostuser_socket_dir": "/var/run/openvswitch",
                "vhostuser_ovs_plug": True,
                "vhostuser_mode": "client",
                "vhostuser_socket": "/var/run/openvswitch/vhu$PORT_ID"}}],
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

    # Test data for length of string
    sample_odl_hconfigs_length = {
        "host": "devstack",      # host-id in ODL JSON
        "agent_type": "ODL L2",  # host-type in ODL JSON
                                 # config in ODL JSON
        "configurations": {"supported_vnic_types": [
            {"vnic_type": "normal", "vif_type": "vhostuser",
             "vif_details": {
                 "uuid": "TEST_UUID",
                 "has_datapath_type_netdev": True,
                 "support_vhost_user": True,
                 "port_prefix": "longprefix_",
                 "vhostuser_socket_dir": "/tmp",
                 "vhostuser_ovs_plug": True,
                 "vhostuser_mode": "server",
                 "vhostuser_socket":
                     "/tmp/longprefix_$PORT_ID"
             }}],
            "allowed_network_types": [
                "local", "vlan", "vxlan", "gre"],
            "bridge_mappings": {"physnet1": "br-ex"}}
    }

    # Raw test data for unicode/string comparison
    sample_odl_hconfigs_length_raw = {
        "host": "devstack",
        "agent_type": "ODL L2",
        "configurations": """{"supported_vnic_types": [
            {"vnic_type": "normal", "vif_type": "vhostuser",
             "vif_details": {
                 "uuid": "TEST_UUID",
                 "has_datapath_type_netdev": true,
                 "support_vhost_user": true,
                 "port_prefix": "prefix_",
                 "vhostuser_socket_dir": "/tmp",
                 "vhostuser_ovs_plug": true,
                 "vhostuser_mode": "server",
                 "vhostuser_socket":
                     "/tmp/prefix_$PORT_ID"
             }}],
            "allowed_network_types": [
                "local", "vlan", "vxlan", "gre"],
            "bridge_mappings": {"physnet1": "br-ex"}}"""
    }

    # test data valid  and invalid segments
    test_valid_segment = {
        api.ID: 'API_ID',
        api.NETWORK_TYPE: n_const.TYPE_LOCAL,
        api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    test_invalid_segment = {
        api.ID: 'API_ID',
        api.NETWORK_TYPE: n_const.TYPE_NONE,
        api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    def setUp(self):
        """Setup test."""
        self.useFixture(base.OpenDaylightRestClientFixture())
        self.useFixture(base.OpenDaylightFeaturesFixture())
        self.useFixture(base.OpenDaylightPseudoAgentPrePopulateFixture())
        self.useFixture(OpenDaylightAgentDBFixture())
        super(TestPseudoAgentDBBindingController, self).setUp()
        self.useFixture(fixture.CallbackRegistryFixture())
        self.cfg = self.useFixture(config_fixture.Config())

        self.mgr = pseudo_agentdb_binding.PseudoAgentDBBindingController()

    def test_is_valid_segment(self):
        """Validate the _check_segment method."""
        all_network_types = [n_const.TYPE_FLAT, n_const.TYPE_GRE,
                             n_const.TYPE_LOCAL, n_const.TYPE_VXLAN,
                             n_const.TYPE_VLAN, n_const.TYPE_NONE]

        valid_types = {
            network_type
            for network_type in all_network_types
            if self.mgr._is_valid_segment(
                {api.NETWORK_TYPE: network_type},
                {'allowed_network_types': [
                    n_const.TYPE_LOCAL, n_const.TYPE_GRE,
                    n_const.TYPE_VXLAN, n_const.TYPE_VLAN]})}

        self.assertEqual({
            n_const.TYPE_LOCAL, n_const.TYPE_GRE, n_const.TYPE_VXLAN,
            n_const.TYPE_VLAN}, valid_types)

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

    def test_bind_port_with_vif_type_ovs_with_sriov_offload(self):
        """test bind_port with vanilla ovs with SR-IOV offload"""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment])

        vif_type = portbindings.VIF_TYPE_OVS
        vif_details = {'some_test_details': None}

        self.mgr._hconfig_bind_port(
            port_context, self.sample_hconfig_dbget_ovs_sriov_offload)

        port_context.set_binding.assert_called_once_with(
            self.test_valid_segment[api.ID], vif_type,
            vif_details, status=n_const.PORT_STATUS_ACTIVE)

    def _set_pass_vif_details(self, port_context, vif_details):
        """extract vif_details and update vif_details if needed."""
        vhostuser_socket_dir = vif_details.get(
            'vhostuser_socket_dir', '/var/run/openvswitch')
        port_spec = vif_details.get(
            'port_prefix', 'vhu') + port_context.current['id']
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

    def _test_bind_port_failed_when_agent_dead(self, hconfig):
        hconfig['alive'] = False
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment],
            host_agents=[hconfig])
        self.mgr.bind_port(port_context)
        port_context.set_binding.assert_not_called()

    def test_bind_port_failed_when_agent_dead_vpp(self):
        hconfig = deepcopy(self.sample_hconf_str_tmpl_subs_vpp)
        self._test_bind_port_failed_when_agent_dead(hconfig)

    def test_bind_port_failed_when_agent_dead_ovs(self):
        hconfig = deepcopy(self.sample_hconf_str_tmpl_subs_ovs)
        self._test_bind_port_failed_when_agent_dead(hconfig)

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

    def test_str_template_substitution_length_in_configuration_string(self):
        """Test for identifier substitution in config JSON string."""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment])

        hconf_dict = self.mgr._substitute_hconfig_tmpl(
            port_context, self.sample_odl_hconfigs_length)

        test_string = hconf_dict['configurations'][
            'supported_vnic_types'][0][
            'vif_details'][portbindings.VHOST_USER_SOCKET]

        expected_str = Template('/tmp/longprefix_$PORT_ID')
        expected_str = expected_str.safe_substitute({
            'PORT_ID': port_context.current['id']})

        self.assertNotEqual(expected_str, test_string)
        self.assertEqual(len(test_string) - len('/tmp/'), 14)

    def test_template_substitution_in_raw_configuration(self):
        """Test for identifier substitution in config string."""
        port_context = self._fake_port_context(
            fake_segments=[self.test_invalid_segment, self.test_valid_segment])

        # Substitute raw string configuration with json
        raw_configurations = self.sample_odl_hconfigs_length_raw[
            'configurations']
        raw_configurations_json = jsonutils.loads(raw_configurations)
        self.sample_odl_hconfigs_length_raw['configurations'] = (
            raw_configurations_json)

        hconf_dict = self.mgr._substitute_hconfig_tmpl(
            port_context, self.sample_odl_hconfigs_length_raw)

        test_string = hconf_dict['configurations'][
            'supported_vnic_types'][0][
                'vif_details'][portbindings.VHOST_USER_SOCKET]

        expected_str = Template('/tmp/prefix_$PORT_ID')
        expected_str = expected_str.safe_substitute({
            'PORT_ID': port_context.current['id']})

        self.assertEqual(expected_str, test_string)

    def _fake_port_context(self, fake_segments, host_agents=None):
        network = mock.MagicMock(spec=api.NetworkContext)
        return mock.MagicMock(
            spec=ctx.PortContext,
            current={'id': 'PORTID',
                     portbindings.VNIC_TYPE: portbindings.VNIC_NORMAL},
            segments_to_bind=fake_segments, network=network,
            host_agents=lambda agent_type: host_agents,
            _plugin_context=mock.MagicMock()
        )

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component')
    def test_prepare_inital_port_status_no_websocket(
            self, mocked_add_provisioning_component):
        port_ctx = self._fake_port_context(
            fake_segments=[self.test_valid_segment])
        initial_port_status = self.mgr._prepare_initial_port_status(port_ctx)
        self.assertEqual(initial_port_status, n_const.PORT_STATUS_ACTIVE)
        mocked_add_provisioning_component.assert_not_called()

    @mock.patch.object(provisioning_blocks, 'add_provisioning_component')
    def test_prepare_inital_port_status_with_websocket(
            self, mocked_add_provisioning_component):
        feature_json = """{"features": {"feature":
                            [{"service-provider-feature":
                            "neutron-extensions:operational-port-status"}]}}"""
        self.cfg.config(odl_features_json=feature_json, group='ml2_odl')
        self.addCleanup(odl_features.deinit)
        odl_features.init()
        port_ctx = self._fake_port_context(
            fake_segments=[self.test_valid_segment])
        initial_port_status = self.mgr._prepare_initial_port_status(port_ctx)
        self.assertEqual(initial_port_status, n_const.PORT_STATUS_DOWN)
        mocked_add_provisioning_component.assert_called()


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
        self.useFixture(base.OpenDaylightRestClientFixture())
        self.useFixture(base.OpenDaylightPseudoAgentPrePopulateFixture())
        self.useFixture(OpenDaylightAgentDBFixture())
        super(TestPseudoAgentDBBindingControllerBug1608659, self).setUp(
            plugin='ml2')
        self.worker = pseudo_agentdb_binding.PseudoAgentDBBindingWorker()

    def test_execute_no_exception(self):
        with mock.patch.object(pseudo_agentdb_binding, 'LOG') as mock_log:
            self.worker.update_agents_db(
                self.sample_odl_hconfigs['hostconfigs']['hostconfig'])
            # Assert no exception happened
            self.assertFalse(mock_log.exception.called)


class TestPseudoAgentNeutronWorker(testlib_api.SqlTestCase):
    def setUp(self):
        self.useFixture(base.OpenDaylightRestClientFixture())
        self.useFixture(base.OpenDaylightJournalThreadFixture())
        self.useFixture(base.OpenDaylightFeaturesFixture())
        self.useFixture(base.OpenDaylightPseudoAgentPrePopulateFixture())
        self.cfg = self.useFixture(config_fixture.Config())
        self.mock_periodic_thread = mock.patch.object(
            periodic_task.PeriodicTask, 'start').start()
        super(TestPseudoAgentNeutronWorker, self).setUp()
        self.cfg.config(mechanism_drivers=['opendaylight_v2'], group='ml2')
        self.cfg.config(
            port_binding_controller='pseudo-agentdb-binding', group='ml2_odl')

    def test_get_worker(self):
        workers = ml2_plugin.Ml2Plugin().get_workers()
        self.assertTrue(any(
            isinstance(worker,
                       pseudo_agentdb_binding.PseudoAgentDBBindingWorker)
            for worker in workers))

    def test_worker(self):
        worker = pseudo_agentdb_binding.PseudoAgentDBBindingWorker()
        worker.wait()
        worker.stop()
        worker.reset()

    def test_worker_start_websocket(self):
        self.cfg.config(enable_websocket_pseudo_agentdb=True, group='ml2_odl')
        worker = pseudo_agentdb_binding.PseudoAgentDBBindingWorker()
        with mock.patch.object(
                websocket_client.OpenDaylightWebsocketClient,
                'odl_create_websocket') as mock_odl_create_websocket:
            worker.start()
            mock_odl_create_websocket.assert_called_once()

    def test_worker_start_periodic(self):
        self.cfg.config(enable_websocket_pseudo_agentdb=False, group='ml2_odl')
        worker = pseudo_agentdb_binding.PseudoAgentDBBindingWorker()
        with mock.patch.object(
                periodic_task.PeriodicTask, 'start') as mock_start:
            worker.start()
            mock_start.assert_called_once()
