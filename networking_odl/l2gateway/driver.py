# Copyright (c) 2016 Ericsson India Global Service Pvt Ltd.
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

from debtcollector import removals
from oslo_config import cfg
from oslo_log import log as logging

from networking_l2gw.services.l2gateway.common import constants
from networking_l2gw.services.l2gateway import service_drivers
from networking_odl.common import client as odl_client

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')

LOG = logging.getLogger(__name__)

L2GATEWAYS = 'l2-gateways'
L2GATEWAY_CONNECTIONS = 'l2gateway-connections'


@removals.removed_class(
    'OpenDaylightL2gwDriver', version='Queens', removal_version='Rocky',
    message="Usage of V1 drivers is deprecated. Please use V2 instead.")
class OpenDaylightL2gwDriver(service_drivers.L2gwDriver):
    """OpenDaylight L2Gateway Service Driver

    This code is the openstack driver for exciting the OpenDaylight L2GW
    facility.
    """

    def __init__(self, service_plugin, validator=None):
        super(OpenDaylightL2gwDriver, self).__init__(service_plugin, validator)
        self.service_plugin = service_plugin
        self.client = odl_client.OpenDaylightRestClient.create_client()
        LOG.warning(
            "ODL: OpenDaylight L2gateway driver has been deprecated "
            "and will be removed. Switch to driver_v2.")

    @property
    def service_type(self):
        return constants.L2GW

    def create_l2_gateway_postcommit(self, context, l2_gateway):
        LOG.info("ODL: Create L2Gateway %(l2gateway)s",
                 {'l2gateway': l2_gateway})
        request = {'l2_gateway': l2_gateway}
        self.client.sendjson('post', L2GATEWAYS, request)

    def delete_l2_gateway_postcommit(self, context, l2_gateway_id):
        LOG.info("ODL: Delete L2Gateway %(l2gatewayid)s",
                 {'l2gatewayid': l2_gateway_id})
        url = L2GATEWAYS + '/' + l2_gateway_id
        self.client.try_delete(url)

    def update_l2_gateway_postcommit(self, context, l2_gateway):
        LOG.info("ODL: Update L2Gateway %(l2gateway)s",
                 {'l2gateway': l2_gateway})
        request = {'l2_gateway': l2_gateway}
        url = L2GATEWAYS + '/' + l2_gateway['id']
        self.client.sendjson('put', url, request)

    def create_l2_gateway_connection_postcommit(self, context,
                                                l2_gateway_connection):
        LOG.info("ODL: Create L2Gateway connection %(l2gwconn)s",
                 {'l2gwconn': l2_gateway_connection})
        odl_l2_gateway_connection = copy.deepcopy(l2_gateway_connection)
        odl_l2_gateway_connection['gateway_id'] = (
            l2_gateway_connection['l2_gateway_id'])
        odl_l2_gateway_connection.pop('l2_gateway_id')
        request = {'l2gateway_connection': odl_l2_gateway_connection}
        self.client.sendjson('post', L2GATEWAY_CONNECTIONS, request)

    def delete_l2_gateway_connection_postcommit(self, context,
                                                l2_gateway_connection_id):
        LOG.info("ODL: Delete L2Gateway connection %(l2gwconnid)s",
                 {'l2gwconnid': l2_gateway_connection_id})
        url = L2GATEWAY_CONNECTIONS + '/' + l2_gateway_connection_id
        self.client.try_delete(url)
