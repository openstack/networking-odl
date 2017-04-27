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

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from networking_sfc.services.flowclassifier.drivers import base as fc_driver

from networking_odl.common import client as odl_client
from networking_odl.common import constants as odl_const

LOG = logging.getLogger(__name__)


class OpenDaylightSFCFlowClassifierDriverV1(
        fc_driver.FlowClassifierDriverBase):

    """OpenDaylight SFC Flow Classifier Driver for networking-sfc.

    This Driver pass through SFC Flow Classifier API calls to
    OpenDaylight Neutron Northbound Project by using the REST
    API's exposed by the project.
    """

    def initialize(self):
        LOG.debug("Initializing OpenDaylight Networking "
                  "SFC Flow Classifier driver")
        self.client = odl_client.OpenDaylightRestClient.create_client()

    @log_helpers.log_method_call
    def create_flow_classifier(self, context):
        self.client.send_request(odl_const.ODL_CREATE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_FLOW_CLASSIFIER,
                                 context.current)

    @log_helpers.log_method_call
    def update_flow_classifier(self, context):
        self.client.send_request(odl_const.ODL_UPDATE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_FLOW_CLASSIFIER,
                                 context.current)

    @log_helpers.log_method_call
    def delete_flow_classifier(self, context):
        self.client.send_request(odl_const.ODL_DELETE,
                                 odl_const.ODL_SFC,
                                 odl_const.ODL_SFC_FLOW_CLASSIFIER,
                                 context.current)

    @log_helpers.log_method_call
    def create_flow_classifier_precommit(self, context):
        LOG.info("Skipping precommit check.")
