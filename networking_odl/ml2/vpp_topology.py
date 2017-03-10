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


import collections
import os

from oslo_log import log
import six
from six.moves.urllib import parse

from neutron.common import constants as n_const
from neutron.extensions import portbindings
from neutron.plugins.common import constants
from neutron.plugins.ml2 import driver_api

from networking_odl.ml2 import network_topology


LOG = log.getLogger(__name__)
HC_VPP_CAPABILITY = 'honeycomb:params:xml:ns:yang:vpp:data:'

class VppNetworkTopologyParser(network_topology.NetworkTopologyParser):

    def new_element(self, devname):
        return VppNetworkTopologyElement(devname=devname)

    def parse_network_topology(self, network_topologies):
        LOG.debug("Parsing Topology using VPP Topology Parser")
        elements_by_name = collections.OrderedDict()
        for topology in network_topologies[
                'network-topology']['topology']:
            if topology['topology-id'].startswith('topology-netconf'):
                for node in topology['node']:
                    # expected url format: ovsdb://uuid/<uuid>[/<path>]]
                    # expected :
                    # "node-id": "name",
                    # "netconf-node-topology:host": "172.21.174.41"
                    # "netconf-node-topology:available-capabilities": {
                    #       "available-capability" : contains the v3po model
                    node_name = node['node-id']
                    LOG.debug("Examining capabilities for node: %s\n",
                              node_name)
                    try:
                        capabilities = node[
                        'netconf-node-topology:available-capabilities']
                        LOG.debug("Node's capabilities: %s\n",
                                  capabilities)
                        for item in capabilities['available-capability']:
                            if HC_VPP_CAPABILITY in item:
                                LOG.debug("Found VPP matching capability for "
                                          "node: %s\n", node_name)
                                element = elements_by_name.get(node_name)
                                if element is None:
                                    elements_by_name[node_name] = element =\
                                        self.new_element(node_name)

                                self.\
                                    _update_element_from_json_netconf_topology_node(
                                    node, element, node_name, capabilities)
                    except KeyError:
                        LOG.debug("No netconf available capabilities found for"
                                  ": %s\n", node_name)

        # Can there can be more VPP instances connected beside the same IP
        # address?
        # Cache will yield more instaces for the same key
        for __, element in six.iteritems(elements_by_name):
            yield element

    def _update_element_from_json_netconf_topology_node(
            self, node, element, node_name, capabilities=None):

        # fetch remote IP address
        element.remote_ip = node["netconf-node-topology:host"]
        # Assume Honeycomb supports vhost_user?
        element.support_vhost_user = True

        LOG.debug(
            'Topology element updated:\n'
            ' - VPP node name: %(node_name)r\n'
            ' - remote_ip: %(remote_ip)r\n'
            ' - support_vhost_user: %(support_vhost_user)r',
            {'node_name': node_name,
             'remote_ip': element.remote_ip,
             'support_vhost_user': element.support_vhost_user})



class VppNetworkTopologyElement(network_topology.NetworkTopologyElement):

    devname = None
    remote_ip = None  # it can be None or a string
    has_datapath_type_netdev = False  # it can be False or True
    support_vhost_user = False  # it can be False or True

    # location for vhostuser sockets.
    # TODO (wdec): This should be configurable in the config probably.
    vhostuser_socket_dir = '/tmp/'

    # TODO (wdec): And also this should be configurable...
    # prefix for port
    port_prefix = 'socket_'

    def __init__(self, **kwargs):
        for name, value in six.iteritems(kwargs):
            setattr(self, name, value)

    @property
    def host_addresses(self):
        # For now it support only the remote IP found in connection info
        return self.remote_ip,

    @property
    def valid_vif_types(self):
        return [portbindings.VIF_TYPE_VHOST_USER]

    def bind_port(self, port_context, vif_type, vif_details):

        port_context_id = port_context.current['id']
        network_context_id = port_context.network.current['id']

        # Bind port to the first valid segment
        for segment in port_context.segments_to_bind:
            if self._is_valid_segment(segment):
                # Guest best VIF type for given host
                vif_details = self._get_vif_details(
                    vif_details=vif_details, port_context_id=port_context_id,
                    vif_type=vif_type)
                LOG.debug(
                    'Bind port with valid segment:\n'
                    '\tport: %(port)r\n'
                    '\tnetwork: %(network)r\n'
                    '\tsegment: %(segment)r\n'
                    '\tVIF type: %(vif_type)r\n'
                    '\tVIF details: %(vif_details)r',
                    {'port': port_context_id,
                     'network': network_context_id,
                     'segment': segment, 'vif_type': vif_type,
                     'vif_details': vif_details})
                port_context.set_binding(
                    segment[driver_api.ID], vif_type, vif_details,
                    status=n_const.PORT_STATUS_ACTIVE)
                return

        raise ValueError('Unable to find any valid segment in given context.')

    def to_dict(self):
        data = super(VppNetworkTopologyElement, self).to_dict()
        data.update(
            {'uuid': self.devname,
             'has_datapath_type_netdev': self.has_datapath_type_netdev,
             'support_vhost_user': self.support_vhost_user,
             'valid_vif_types': self.valid_vif_types})
        if portbindings.VIF_TYPE_VHOST_USER in self.valid_vif_types:
            data.update({'port_prefix': self.port_prefix,
                         'vhostuser_socket_dir': self.vhostuser_socket_dir})
        return data

    def _is_valid_segment(self, segment):
        """Verify a segment is valid for the OpenDaylight MechanismDriver.

        Verify the requested segment is supported by ODL and return True or
        False to indicate this to callers.
        """

        network_type = segment[driver_api.NETWORK_TYPE]
        return network_type in [constants.TYPE_LOCAL, constants.TYPE_GRE,
                                constants.TYPE_VXLAN, constants.TYPE_VLAN]

    def _get_vif_details(self, vif_details, port_context_id, vif_type):
        vif_details = dict(vif_details)
        if vif_type == portbindings.VIF_TYPE_VHOST_USER:
            socket_path = os.path.join(
                self.vhostuser_socket_dir,
                (self.port_prefix + port_context_id)) #Why the splice? [:14])

            vif_details.update({
                portbindings.VHOST_USER_MODE:
                portbindings.VHOST_USER_MODE_CLIENT,
                #portbindings.VHOST_USER_OVS_PLUG: True,
                portbindings.VHOST_USER_SOCKET: socket_path
            })
        return vif_details

    def __setattr__(self, name, value):
        # raises Attribute error if the class hasn't this attribute
        getattr(type(self), name)
        super(VppNetworkTopologyElement, self).__setattr__(name, value)
