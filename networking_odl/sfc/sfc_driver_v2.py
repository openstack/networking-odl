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

from oslo_log import log as logging

from networking_sfc.services.sfc.drivers import base as sfc_driver

from networking_odl.common import constants as odl_const
from networking_odl.journal import journal

LOG = logging.getLogger(__name__)


class OpenDaylightSFCDriverV2(sfc_driver.SfcDriverBase):
    """OpenDaylight SFC Driver (Version 2) for networking-sfc.

    Driver sends REST request for Networking SFC Resources (Port Pair,
    Port Pair Group & Port Chain) to OpenDaylight Neutron Northbound.
    OpenDaylight Neutron Northbound has API's defined for these resources
    based on the Networking SFC APIs.
    """

    def initialize(self):
        LOG.debug("Initializing OpenDaylight Networking SFC driver(Version 2)")
        self.journal = journal.OpendaylightJournalThread()

    @staticmethod
    def _record_in_journal(context, object_type, operation, data=None):
        if data is None:
            data = context.current
        journal.record(context._plugin_context, context, object_type,
                       context.current['id'], operation, data)

    def create_port_pair_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR, odl_const.ODL_CREATE)

    def create_port_pair_group_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR_GROUP, odl_const.ODL_CREATE)

    def create_port_chain_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_CHAIN, odl_const.ODL_CREATE)

    def update_port_pair_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR, odl_const.ODL_UPDATE)

    def update_port_pair_group_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR_GROUP, odl_const.ODL_UPDATE)

    def update_port_chain_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_CHAIN, odl_const.ODL_UPDATE)

    def delete_port_pair_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR, odl_const.ODL_DELETE,
            data=[])

    def delete_port_pair_group_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_PAIR_GROUP, odl_const.ODL_DELETE,
            data=[])

    def delete_port_chain_precommit(self, context):
        OpenDaylightSFCDriverV2._record_in_journal(
            context, odl_const.ODL_SFC_PORT_CHAIN, odl_const.ODL_DELETE,
            data=[])

    def _postcommit(self, context):
        self.journal.set_sync_event()

    create_port_pair_postcommit = _postcommit
    create_port_pair_group_postcommit = _postcommit
    create_port_chain_postcommit = _postcommit
    update_port_pair_postcommit = _postcommit
    update_port_pair_group_postcommit = _postcommit
    update_port_chain_postcommit = _postcommit
    delete_port_pair_postcommit = _postcommit
    delete_port_pair_group_postcommit = _postcommit
    delete_port_chain_postcommit = _postcommit

    # Need to implement these methods, else driver loading fails with error
    # complaining about no abstract method implementation present.
    def create_port_pair(self, context):
        super(OpenDaylightSFCDriverV2, self).create_port_pair(context)

    def create_port_pair_group(self, context):
        super(OpenDaylightSFCDriverV2, self).create_port_pair_group(context)

    def create_port_chain(self, context):
        super(OpenDaylightSFCDriverV2, self).create_port_chain(context)

    def update_port_pair(self, context):
        super(OpenDaylightSFCDriverV2, self).update_port_pair(context)

    def update_port_pair_group(self, context):
        super(OpenDaylightSFCDriverV2, self).update_port_pair_group(context)

    def update_port_chain(self, context):
        super(OpenDaylightSFCDriverV2, self).update_port_chain(context)

    def delete_port_pair(self, context):
        super(OpenDaylightSFCDriverV2, self).delete_port_pair(context)

    def delete_port_pair_group(self, context):
        super(OpenDaylightSFCDriverV2, self).delete_port_pair_group(context)

    def delete_port_chain(self, context):
        super(OpenDaylightSFCDriverV2, self).delete_port_chain(context)
