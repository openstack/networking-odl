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

from unittest import mock

from neutron.plugins.ml2 import driver_context as ctx
from neutron_lib.api.definitions import portbindings
from neutron_lib import constants as n_constants
from neutron_lib.plugins.ml2 import api

from networking_odl.ml2 import legacy_port_binding
from networking_odl.tests import base


class TestLegacyPortBindingManager(base.DietTestCase):
    # valid  and invalid segments
    valid_segment = {
        api.ID: 'API_ID',
        api.NETWORK_TYPE: n_constants.TYPE_LOCAL,
        api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    invalid_segment = {
        api.ID: 'API_ID',
        api.NETWORK_TYPE: n_constants.TYPE_NONE,
        api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    def test_check_segment(self):
        """Validate the _check_segment method."""

        all_network_types = [n_constants.TYPE_FLAT, n_constants.TYPE_GRE,
                             n_constants.TYPE_LOCAL, n_constants.TYPE_VXLAN,
                             n_constants.TYPE_VLAN, n_constants.TYPE_NONE]

        mgr = legacy_port_binding.LegacyPortBindingManager()

        valid_types = {
            network_type
            for network_type in all_network_types
            if mgr._check_segment({api.NETWORK_TYPE: network_type})}

        self.assertEqual({
            n_constants.TYPE_FLAT, n_constants.TYPE_LOCAL,
            n_constants.TYPE_GRE, n_constants.TYPE_VXLAN,
            n_constants.TYPE_VLAN}, valid_types)

    def test_bind_port(self):

        network = mock.MagicMock(spec=api.NetworkContext)

        port_context = mock.MagicMock(
            spec=ctx.PortContext, current={'id': 'CURRENT_CONTEXT_ID'},
            segments_to_bind=[self.valid_segment, self.invalid_segment],
            network=network)

        mgr = legacy_port_binding.LegacyPortBindingManager()
        vif_type = mgr._get_vif_type(port_context)

        mgr.bind_port(port_context)

        port_context.set_binding.assert_called_once_with(
            self.valid_segment[api.ID], vif_type,
            mgr.vif_details, status=n_constants.PORT_STATUS_ACTIVE)

    def test_bind_port_unsupported_vnic_type(self):
        network = mock.MagicMock(spec=api.NetworkContext)
        port_context = mock.MagicMock(
            spec=ctx.PortContext,
            current={'id': 'CURRENT_CONTEXT_ID',
                     portbindings.VNIC_TYPE: portbindings.VNIC_DIRECT},
            segments_to_bind=[self.valid_segment, self.invalid_segment],
            network=network)

        mgr = legacy_port_binding.LegacyPortBindingManager()
        mgr.bind_port(port_context)
        port_context.set_binding.assert_not_called()
