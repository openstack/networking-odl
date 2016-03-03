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

import abc
import copy

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
import six

from networking_l2gw.services.l2gateway.common import constants
from networking_l2gw.services.l2gateway import service_drivers
from networking_odl._i18n import _LE, _LI
from networking_odl.common import client as odl_client

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')

LOG = logging.getLogger(__name__)

L2GATEWAYS = 'l2-gateways'
L2GATEWAY_CONNECTIONS = 'l2gateway-connections'


@six.add_metaclass(abc.ABCMeta)
class OpenDaylightL2gwDriver(service_drivers.L2gwDriver):
    """Opendaylight L2Gateway Service Driver

    This code is the openstack driver for exciting the OpenDaylight L2GW
    facility.
    """

    def __init__(self, service_plugin, validator=None):
        super(OpenDaylightL2gwDriver, self).__init__(service_plugin, validator)
        self.service_plugin = service_plugin
        self.client = odl_client.OpenDaylightRestClient.create_client()
        LOG.info(_LI("ODL: Started OpenDaylight L2Gateway driver"))

    @property
    def service_type(self):
        return constants.L2GW

    def create_l2_gateway_postcommit(self, context, l2_gateway):
        LOG.info(_LI("ODL: Create L2Gateway %(l2gateway)s"),
                 {'l2gateway': l2_gateway})
        request = {'l2_gateway': l2_gateway}
        try:
            self.client.sendjson('post', L2GATEWAYS, request)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("ODL: L2Gateway create"
                                  " failed for gateway %(l2gatewayid)s"),
                              {'l2gatewayid': l2_gateway['id']})

    def delete_l2_gateway_postcommit(self, context, l2_gateway_id):
        LOG.info(_LI("ODL: Delete L2Gateway %(l2gatewayid)s"),
                 {'l2gatewayid': l2_gateway_id})
        url = L2GATEWAYS + '/' + l2_gateway_id
        try:
            self.client.try_delete(url)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("ODL: L2Gateway delete"
                                  " failed for gateway_id %(l2gatewayid)s"),
                              {'l2gatewayid': l2_gateway_id})

    def update_l2_gateway_postcommit(self, context, l2_gateway):
        LOG.info(_LI("ODL: Update L2Gateway %(l2gateway)s"),
                 {'l2gateway': l2_gateway})
        request = {'l2_gateway': l2_gateway}
        url = L2GATEWAYS + '/' + l2_gateway['id']
        try:
            self.client.sendjson('put', url, request)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("ODL: L2Gateway update"
                                  " failed for gateway %(l2gatewayid)s"),
                              {'l2gatewayid': l2_gateway['id']})

    def create_l2_gateway_connection_postcommit(self, context,
                                                l2_gateway_connection):
        LOG.info(_LI("ODL: Create L2Gateway connection %(l2gwconn)s"),
                 {'l2gwconn': l2_gateway_connection})
        odl_l2_gateway_connection = copy.deepcopy(l2_gateway_connection)
        odl_l2_gateway_connection['gateway_id'] = (
            l2_gateway_connection['l2_gateway_id'])
        odl_l2_gateway_connection.pop('l2_gateway_id')
        request = {'l2gateway_connection': odl_l2_gateway_connection}
        try:
            self.client.sendjson('post', L2GATEWAY_CONNECTIONS, request)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("ODL: L2Gateway connection create"
                                  " failed for gateway %(l2gwconnid)s"),
                              {'l2gwconnid':
                               l2_gateway_connection['l2_gateway_id']})

    def delete_l2_gateway_connection_postcommit(self, context,
                                                l2_gateway_connection_id):
        LOG.info(_LI("ODL: Delete L2Gateway connection %(l2gwconnid)s"),
                 {'l2gwconnid': l2_gateway_connection_id})
        url = L2GATEWAY_CONNECTIONS + '/' + l2_gateway_connection_id
        try:
            self.client.try_delete(url)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("ODL: L2Gateway connection delete"
                                  " failed for connection %(l2gwconnid)s"),
                              {'l2gwconnid': l2_gateway_connection_id})
