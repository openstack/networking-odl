# Copyright (c) 2016 Brocade Communication Systems
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

from debtcollector import removals

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from networking_sfc.services.sfc.drivers import base as sfc_driver

from networking_odl.common import client as odl_client
from networking_odl.common import constants as odl_const

LOG = logging.getLogger(__name__)


@removals.removed_class(
    'OpenDaylightSFCDriverV1', version='Queens', removal_version='Rocky',
    message="Usage of V1 drivers is deprecated. Please use V2 instead.")
class OpenDaylightSFCDriverV1(sfc_driver.SfcDriverBase):
    """OpenDaylight SFC Driver for networking-sfc.

    Driver sends REST request for Networking SFC Resources (Port Pair,
    Port Pair Group & Port Chain) to OpenDaylight Neutron Northbound.
    OpenDaylight Neutron Northbound has API's defined for these resources
    based on the Networking SFC APIs.
    """

    def initialize(self):
        LOG.debug("Initializing OpenDaylight Networking SFC driver")
        self.client = odl_client.OpenDaylightRestClient.create_client()

    @log_helpers.log_method_call
    def create_port_pair(self, context):
        self.client.send_request(odl_const.ODL_CREATE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_PAIR,
                                 context.current)

    @log_helpers.log_method_call
    def update_port_pair(self, context):
        self.client.send_request(odl_const.ODL_UPDATE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_PAIR,
                                 context.current)

    @log_helpers.log_method_call
    def delete_port_pair(self, context):
        self.client.send_request(odl_const.ODL_DELETE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_PAIR,
                                 context.current)

    @log_helpers.log_method_call
    def create_port_pair_group(self, context):
        self.client.send_request(odl_const.ODL_CREATE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_PAIR_GROUP,
                                 context.current)

    @log_helpers.log_method_call
    def update_port_pair_group(self, context):
        self.client.send_request(odl_const.ODL_UPDATE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_PAIR_GROUP,
                                 context.current)

    @log_helpers.log_method_call
    def delete_port_pair_group(self, context):
        self.client.send_request(odl_const.ODL_DELETE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_PAIR_GROUP,
                                 context.current)

    @log_helpers.log_method_call
    def create_port_chain(self, context):
        self.client.send_request(odl_const.ODL_CREATE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_CHAIN,
                                 context.current)

    @log_helpers.log_method_call
    def update_port_chain(self, context):
        self.client.send_request(odl_const.ODL_UPDATE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_CHAIN,
                                 context.current)

    @log_helpers.log_method_call
    def delete_port_chain(self, context):
        self.client.send_request(odl_const.ODL_DELETE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_PORT_CHAIN,
                                 context.current)
