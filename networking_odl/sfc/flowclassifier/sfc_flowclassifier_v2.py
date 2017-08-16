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

from networking_sfc.extensions import flowclassifier as fc_const
from networking_sfc.services.flowclassifier.drivers import base as fc_driver

from networking_odl.common import constants as odl_const
from networking_odl.common import postcommit
from networking_odl.journal import full_sync
from networking_odl.journal import journal

LOG = logging.getLogger(__name__)

SFC_FC_RESOURCES = {
    odl_const.ODL_SFC_FLOW_CLASSIFIER:
        odl_const.NETWORKING_SFC_FLOW_CLASSIFIERS,
}


@postcommit.add_postcommit('flow_classifier')
class OpenDaylightSFCFlowClassifierDriverV2(
        fc_driver.FlowClassifierDriverBase):

    """OpenDaylight SFC Flow Classifier Driver (Version 2) for networking-sfc.

    This Driver pass through SFC Flow Classifier API calls to
    OpenDaylight Neutron Northbound Project by using the REST
    API's exposed by the project.
    """

    def initialize(self):
        LOG.debug("Initializing OpenDaylight Networking "
                  "SFC Flow Classifier driver Version 2")
        self.journal = journal.OpenDaylightJournalThread()
        full_sync.register(fc_const.FLOW_CLASSIFIER_EXT, SFC_FC_RESOURCES)

    @staticmethod
    def _record_in_journal(context, object_type, operation, data=None):
        if data is None:
            data = context.current
        journal.record(context._plugin_context, object_type,
                       context.current['id'], operation, data)

    @log_helpers.log_method_call
    def create_flow_classifier_precommit(self, context):
        OpenDaylightSFCFlowClassifierDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_FLOW_CLASSIFIER, odl_const.ODL_CREATE)

    @log_helpers.log_method_call
    def update_flow_classifier_precommit(self, context):
        OpenDaylightSFCFlowClassifierDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_FLOW_CLASSIFIER, odl_const.ODL_UPDATE)

    @log_helpers.log_method_call
    def delete_flow_classifier_precommit(self, context):
        OpenDaylightSFCFlowClassifierDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_FLOW_CLASSIFIER, odl_const.ODL_DELETE,
            data=[])

    # Need to implement these methods, else driver loading fails with error
    # complaining about no abstract method implementation present.
    @log_helpers.log_method_call
    def create_flow_classifier(self, context):
        super(OpenDaylightSFCFlowClassifierDriverV2,
              self).create_flow_classifier(context)

    @log_helpers.log_method_call
    def update_flow_classifier(self, context):
        super(OpenDaylightSFCFlowClassifierDriverV2,
              self).update_flow_classifier(context)

    @log_helpers.log_method_call
    def delete_flow_classifier(self, context):
        super(OpenDaylightSFCFlowClassifierDriverV2,
              self).delete_flow_classifier(context)
