# Copyright (c) 2017 Brocade Communication Systems
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

from networking_sfc.extensions import sfc as sfc_const
from networking_sfc.services.sfc.drivers import base as sfc_driver

from networking_odl.common import constants as odl_const
from networking_odl.common import postcommit
from networking_odl.journal import full_sync
from networking_odl.journal import journal

LOG = logging.getLogger(__name__)

SFC_RESOURCES = {
    odl_const.ODL_SFC_PORT_PAIR: odl_const.NETWORKING_SFC_PORT_PAIRS,
    odl_const.ODL_SFC_PORT_PAIR_GROUP:
        odl_const.NETWORKING_SFC_PORT_PAIR_GROUPS,
    odl_const.ODL_SFC_PORT_CHAIN: odl_const.NETWORKING_SFC_PORT_CHAINS
}


@postcommit.add_postcommit('port_pair', 'port_pair_group', 'port_chain')
class OpenDaylightSFCDriverV2(sfc_driver.SfcDriverBase):
    """OpenDaylight SFC Driver (Version 2) for networking-sfc.

    Driver sends REST request for Networking SFC Resources (Port Pair,
    Port Pair Group & Port Chain) to OpenDaylight Neutron Northbound.
    OpenDaylight Neutron Northbound has API's defined for these resources
    based on the Networking SFC APIs.
    """

    def initialize(self):
        LOG.debug("Initializing OpenDaylight Networking SFC driver(Version 2)")
        self.journal = journal.OpenDaylightJournalThread()
        full_sync.register(sfc_const.SFC_EXT, SFC_RESOURCES)

    @staticmethod
    def _record_in_journal(context, object_type, operation, data=None):
        if data is None:
            data = context.current
        journal.record(context._plugin_context, object_type,
                       context.current['id'], operation, data)

    @log_helpers.log_method_call
    def create_port_pair_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR, odl_const.ODL_CREATE)

    @log_helpers.log_method_call
    def create_port_pair_group_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR_GROUP, odl_const.ODL_CREATE)

    @log_helpers.log_method_call
    def create_port_chain_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_CHAIN, odl_const.ODL_CREATE)

    @log_helpers.log_method_call
    def update_port_pair_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR, odl_const.ODL_UPDATE)

    @log_helpers.log_method_call
    def update_port_pair_group_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR_GROUP, odl_const.ODL_UPDATE)

    @log_helpers.log_method_call
    def update_port_chain_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_CHAIN, odl_const.ODL_UPDATE)

    @log_helpers.log_method_call
    def delete_port_pair_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR, odl_const.ODL_DELETE,
            data=[])

    @log_helpers.log_method_call
    def delete_port_pair_group_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR_GROUP, odl_const.ODL_DELETE,
            data=[])

    @log_helpers.log_method_call
    def delete_port_chain_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_CHAIN, odl_const.ODL_DELETE,
            data=[])

    # Need to implement these methods, else driver loading fails with error
    # complaining about no abstract method implementation present.
    @log_helpers.log_method_call
    def create_port_pair(self, context):
        super(OpenDaylightSFCDriverV2, self).create_port_pair(context)

    @log_helpers.log_method_call
    def create_port_pair_group(self, context):
        super(OpenDaylightSFCDriverV2, self).create_port_pair_group(context)

    @log_helpers.log_method_call
    def create_port_chain(self, context):
        super(OpenDaylightSFCDriverV2, self).create_port_chain(context)

    @log_helpers.log_method_call
    def update_port_pair(self, context):
        super(OpenDaylightSFCDriverV2, self).update_port_pair(context)

    @log_helpers.log_method_call
    def update_port_pair_group(self, context):
        super(OpenDaylightSFCDriverV2, self).update_port_pair_group(context)

    @log_helpers.log_method_call
    def update_port_chain(self, context):
        super(OpenDaylightSFCDriverV2, self).update_port_chain(context)

    @log_helpers.log_method_call
    def delete_port_pair(self, context):
        super(OpenDaylightSFCDriverV2, self).delete_port_pair(context)

    @log_helpers.log_method_call
    def delete_port_pair_group(self, context):
        super(OpenDaylightSFCDriverV2, self).delete_port_pair_group(context)

    @log_helpers.log_method_call
    def delete_port_chain(self, context):
        super(OpenDaylightSFCDriverV2, self).delete_port_chain(context)
