# Copyright (c) 2017 Ericsson India Global Service Pvt Ltd.
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

import copy

from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from networking_l2gw.services.l2gateway.common import constants
from networking_l2gw.services.l2gateway import service_drivers
from networking_odl.common import constants as odl_const
from networking_odl.common import postcommit
from networking_odl.journal import full_sync
from networking_odl.journal import journal


cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')

LOG = logging.getLogger(__name__)

L2GW_RESOURCES = {
    odl_const.ODL_L2GATEWAY: odl_const.ODL_L2GATEWAYS,
    odl_const.ODL_L2GATEWAY_CONNECTION: odl_const.ODL_L2GATEWAY_CONNECTIONS
}


@postcommit.add_postcommit('l2_gateway', 'l2_gateway_connection')
class OpenDaylightL2gwDriver(service_drivers.L2gwDriver):
    """OpenDaylight L2Gateway Service Driver

    This code is the openstack driver for exciting the OpenDaylight L2GW
    facility.
    """

    def __init__(self, service_plugin, validator=None):
        super(OpenDaylightL2gwDriver, self).__init__(service_plugin, validator)
        self.service_plugin = service_plugin
        self.journal = journal.OpenDaylightJournalThread()
        full_sync.register(constants.L2GW, L2GW_RESOURCES)
        LOG.info("ODL: Started OpenDaylight L2Gateway V2 driver")

    @property
    def service_type(self):
        return constants.L2GW

    @log_helpers.log_method_call
    def create_l2_gateway_precommit(self, context, l2_gateway):
        journal.record(context, odl_const.ODL_L2GATEWAY,
                       l2_gateway['id'], odl_const.ODL_CREATE,
                       l2_gateway)

    @log_helpers.log_method_call
    def update_l2_gateway_precommit(self, context, l2_gateway):
        journal.record(context, odl_const.ODL_L2GATEWAY,
                       l2_gateway['id'], odl_const.ODL_UPDATE,
                       l2_gateway)

    @log_helpers.log_method_call
    def delete_l2_gateway_precommit(self, context, l2_gateway_id):
        journal.record(context, odl_const.ODL_L2GATEWAY,
                       l2_gateway_id, odl_const.ODL_DELETE,
                       l2_gateway_id)

    @log_helpers.log_method_call
    def create_l2_gateway_connection_precommit(self, context,
                                               l2_gateway_connection):
        odl_l2_gateway_connection = copy.deepcopy(l2_gateway_connection)
        odl_l2_gateway_connection['gateway_id'] = (
            l2_gateway_connection['l2_gateway_id'])
        odl_l2_gateway_connection.pop('l2_gateway_id')
        journal.record(context, odl_const.ODL_L2GATEWAY_CONNECTION,
                       odl_l2_gateway_connection['id'],
                       odl_const.ODL_CREATE,
                       odl_l2_gateway_connection)

    @log_helpers.log_method_call
    def delete_l2_gateway_connection_precommit(self, context,
                                               l2_gateway_connection_id):
        journal.record(context, odl_const.ODL_L2GATEWAY_CONNECTION,
                       l2_gateway_connection_id,
                       odl_const.ODL_DELETE,
                       l2_gateway_connection_id)
