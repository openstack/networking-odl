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

from os import path

import mock
from oslo_log import log
from oslo_serialization import jsonutils

from neutron.common import constants as n_constants
from neutron.extensions import portbindings
from neutron.plugins.common import constants
from neutron.plugins.ml2 import driver_api
from neutron.plugins.ml2 import driver_context

from networking_odl.ml2 import ovsdb_topology
from networking_odl.tests import base


LOG = log.getLogger(__name__)


class TestOvsdbTopologyParser(base.DietTestCase):

    def test_parse_network_topology_ovs(self):
        given_parser = ovsdb_topology.OvsdbNetworkTopologyParser()
        given_topology = self.load_network_topology('ovs_topology.json')

        # when parse topology
        elements = list(given_parser.parse_network_topology(given_topology))

        # then parser yields one element supporting only OVS vif type
        self.assertEqual(
            [{'class':
              'networking_odl.ml2.ovsdb_topology.OvsdbNetworkTopologyElement',
              'has_datapath_type_netdev': False,
              'host_addresses': ['10.237.214.247'],
              'support_vhost_user': False,
              'uuid': 'c4ad780f-8f91-4fa4-804e-dd16beb191e2',
              'valid_vif_types': [portbindings.VIF_TYPE_OVS]}],
            [e.to_dict() for e in elements])

    def test_parse_network_topology_vhostuser(self):
        given_parser = ovsdb_topology.OvsdbNetworkTopologyParser()
        given_topology = self.load_network_topology('vhostuser_topology.json')

        # when parse topology
        elements = list(given_parser.parse_network_topology(given_topology))

        # then parser yields one element supporting VHOSTUSER and OVS vif types
        self.assertEqual(
            [{'class':
              'networking_odl.ml2.ovsdb_topology.OvsdbNetworkTopologyElement',
              'has_datapath_type_netdev': True,
              'host_addresses': ['192.168.66.1'],
              'port_prefix': 'vhu',
              'support_vhost_user': True,
              'uuid': 'c805d82d-a5d8-419d-bc89-6e3713ff9f6c',
              'valid_vif_types': [portbindings.VIF_TYPE_VHOST_USER,
                                  portbindings.VIF_TYPE_OVS],
              'vhostuser_socket_dir': '/var/run/openvswitch'}],
            [e.to_dict() for e in elements])

    def load_network_topology(self, file_name):
        file_path = path.join(path.dirname(__file__), file_name)
        LOG.debug('Loading topology from file: %r', file_path)
        with open(file_path, 'rt') as fd:
            return jsonutils.loads(str(fd.read()), encoding='utf-8')


class TestOvsdbNetworkingTopologyElement(base.DietTestCase):

    # given valid  and invalid segments
    VALID_SEGMENT = {
        driver_api.ID: 'API_ID',
        driver_api.NETWORK_TYPE: constants.TYPE_LOCAL,
        driver_api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        driver_api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    INVALID_SEGMENT = {
        driver_api.ID: 'API_ID',
        driver_api.NETWORK_TYPE: constants.TYPE_NONE,
        driver_api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        driver_api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    segments_to_bind = [INVALID_SEGMENT, VALID_SEGMENT]

    def given_element(self, uuid='some_uuid', **kwargs):
        return ovsdb_topology.OvsdbNetworkTopologyElement(uuid=uuid, **kwargs)

    def test_valid_vif_types_with_no_positive_value(self):
        given_element = self.given_element(
            has_datapath_type_netdev=False, support_vhost_user=False)
        valid_vif_types = given_element.valid_vif_types
        self.assertEqual([portbindings.VIF_TYPE_OVS], valid_vif_types)

    def test_valid_vif_types_with_datapath_type_netdev(self):
        given_element = self.given_element(
            has_datapath_type_netdev=True, support_vhost_user=False)
        valid_vif_types = given_element.valid_vif_types
        self.assertEqual([portbindings.VIF_TYPE_OVS], valid_vif_types)

    def test_valid_vif_types_with_support_vhost_user(self):
        given_element = self.given_element(
            has_datapath_type_netdev=False, support_vhost_user=True)
        valid_vif_types = given_element.valid_vif_types
        self.assertEqual([portbindings.VIF_TYPE_OVS], valid_vif_types)

    def test_valid_vif_types_with_all_positive_values(self):
        given_element = self.given_element(
            has_datapath_type_netdev=True, support_vhost_user=True)
        valid_vif_types = given_element.valid_vif_types
        self.assertEqual(
            [portbindings.VIF_TYPE_VHOST_USER, portbindings.VIF_TYPE_OVS],
            valid_vif_types)

    def test_to_json_ovs(self):
        given_element = self.given_element(
            has_datapath_type_netdev=False, support_vhost_user=True,
            remote_ip='192.168.99.33')
        json = given_element.to_json()
        self.assertEqual(
            {'class':
             'networking_odl.ml2.ovsdb_topology.OvsdbNetworkTopologyElement',
             'uuid': 'some_uuid',
             'host_addresses': ['192.168.99.33'],
             'has_datapath_type_netdev': False,
             'support_vhost_user': True,
             'valid_vif_types': [portbindings.VIF_TYPE_OVS]},
            jsonutils.loads(json))

    def test_to_json_vhost_user(self):
        given_element = self.given_element(
            has_datapath_type_netdev=True, support_vhost_user=True,
            remote_ip='192.168.99.66')
        json = given_element.to_json()
        self.assertEqual(
            {'class':
             'networking_odl.ml2.ovsdb_topology.OvsdbNetworkTopologyElement',
             'uuid': 'some_uuid',
             'host_addresses': ['192.168.99.66'],
             'has_datapath_type_netdev': True,
             'support_vhost_user': True,
             'valid_vif_types':
             [portbindings.VIF_TYPE_VHOST_USER, portbindings.VIF_TYPE_OVS],
             'port_prefix': 'vhu',
             'vhostuser_socket_dir': '/var/run/openvswitch'},
            jsonutils.loads(json))

    def test_set_attr_with_invalid_name(self):
        element = self.given_element()
        self.assertRaises(
            AttributeError, lambda: setattr(element, 'invalid_attribute', 10))

    def test_is_valid_segment(self):
        """Validate the _check_segment method."""

        # given driver and all network types
        given_element = self.given_element(
            has_datapath_type_netdev=True, support_vhost_user=True,
            remote_ip='192.168.99.66')
        all_network_types = [constants.TYPE_FLAT, constants.TYPE_GRE,
                             constants.TYPE_LOCAL, constants.TYPE_VXLAN,
                             constants.TYPE_VLAN, constants.TYPE_NONE]

        # when checking segments network type
        valid_types = {
            network_type
            for network_type in all_network_types
            if given_element._is_valid_segment(
                {driver_api.NETWORK_TYPE: network_type})}

        # then true is returned only for valid network types
        self.assertEqual({
            constants.TYPE_LOCAL, constants.TYPE_GRE, constants.TYPE_VXLAN,
            constants.TYPE_VLAN}, valid_types)

    def test_bind_port_with_vif_type_ovs(self):
        given_port_context = self.given_port_context(
            given_segments=[self.INVALID_SEGMENT, self.VALID_SEGMENT])
        given_element = self.given_element('some_uuid')

        # When bind port
        given_element.bind_port(
            port_context=given_port_context,
            vif_type=portbindings.VIF_TYPE_OVS,
            vif_details={'some_details': None})

        given_port_context.set_binding.assert_called_once_with(
            self.VALID_SEGMENT[driver_api.ID], portbindings.VIF_TYPE_OVS,
            {'some_details': None}, status=n_constants.PORT_STATUS_ACTIVE)

    def test_bind_port_with_vif_type_vhost_user(self):
        given_port_context = self.given_port_context(
            given_segments=[self.INVALID_SEGMENT, self.VALID_SEGMENT])
        given_element = self.given_element('some_uuid')

        # When bind port
        given_element.bind_port(
            port_context=given_port_context,
            vif_type=portbindings.VIF_TYPE_VHOST_USER,
            vif_details={'some_details': None})

        given_port_context.set_binding.assert_called_once_with(
            self.VALID_SEGMENT[driver_api.ID],
            portbindings.VIF_TYPE_VHOST_USER,
            {'vhostuser_socket': '/var/run/openvswitch/vhuCURRENT_CON',
             'some_details': None, 'vhostuser_ovs_plug': True,
             'vhostuser_mode': 'client'},
            status=n_constants.PORT_STATUS_ACTIVE)

    @mock.patch.object(ovsdb_topology, 'LOG')
    def test_bind_port_without_valid_segment(self, logger):
        given_port_context = self.given_port_context(
            given_segments=[self.INVALID_SEGMENT])
        given_element = self.given_element('some_uuid')

        # when port is bound
        self.assertRaises(
            ValueError, lambda: given_element.bind_port(
                port_context=given_port_context,
                vif_type=portbindings.VIF_TYPE_OVS,
                vif_details={'some_details': None}))

        self.assertFalse(given_port_context.set_binding.called)

    def given_port_context(self, given_segments):
        # given NetworkContext
        network = mock.MagicMock(spec=driver_api.NetworkContext)

        # given port context
        return mock.MagicMock(
            spec=driver_context.PortContext,
            current={'id': 'CURRENT_CONTEXT_ID'},
            segments_to_bind=given_segments,
            network=network)
