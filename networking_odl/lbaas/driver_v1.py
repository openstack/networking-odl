#
# Copyright (C) 2013 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#

from oslo_config import cfg
from oslo_log import log as logging

from neutron_lbaas.services.loadbalancer.drivers import abstract_driver

from networking_odl.common import client as odl_client
from networking_odl.common import constants as odl_const

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = logging.getLogger(__name__)
LBAAS = "lbaas"
POOLS_URL_PATH = LBAAS + '/' + odl_const.ODL_POOLS
HEALTHMONITORS_URL_PATH = LBAAS + '/' + odl_const.ODL_HEALTHMONITORS


class OpenDaylightLbaasDriverV1(abstract_driver.LoadBalancerAbstractDriver):

    """OpenDaylight LBaaS Driver for the V1 API

    This code is the backend implementation for the OpenDaylight
    LBaaS V1 driver for OpenStack Neutron.
    """

    def __init__(self, plugin):
        LOG.debug("Initializing OpenDaylight LBaaS driver")
        self.plugin = plugin
        self.client = odl_client.OpenDaylightRestClient.create_client()

    def create_vip(self, context, vip):
        """Create a vip on the OpenDaylight Controller.

        No code related to vip in the OpenDayLight neutronNorthbound,
        so pass this method.
        """
        pass

    def update_vip(self, context, old_vip, vip):
        """Update a vip on the OpenDaylight Controller.

        No code related to vip in the OpenDayLight neutronNorthbound,
        so pass this method.
        """
        pass

    def delete_vip(self, context, vip):
        """Delete a vip on the OpenDaylight Controller.

        No code related to vip in the OpenDayLight neutronNorthbound,
        so pass this method.
        """
        pass

    def create_pool(self, context, pool):
        """Create a pool on the OpenDaylight Controller."""
        url = POOLS_URL_PATH
        self.client.sendjson('post', url, {odl_const.ODL_POOL: pool})

    def update_pool(self, context, old_pool, pool):
        """Update a pool on the OpenDaylight Controller."""
        url = POOLS_URL_PATH + "/" + old_pool['id']
        self.client.sendjson('put', url, {odl_const.ODL_POOL: pool})

    def delete_pool(self, context, pool):
        """Delete a pool on the OpenDaylight Controller."""
        url = POOLS_URL_PATH + "/" + pool['id']
        self.client.sendjson('delete', url, None)

    def create_member(self, context, member):
        """Create a pool member on the OpenDaylight Controller."""
        url = (
            POOLS_URL_PATH + '/' + member['pool_id'] +
            '/' + odl_const.ODL_MEMBERS)
        self.client.sendjson('post', url, {odl_const.ODL_MEMBER: member})

    def update_member(self, context, old_member, member):
        """Update a pool member on the OpenDaylight Controller."""
        url = (
            POOLS_URL_PATH + '/' + member['pool_id'] +
            '/' + odl_const.ODL_MEMBERS + "/" + old_member['id'])
        self.client.sendjson('put', url, {odl_const.ODL_MEMBER: member})

    def delete_member(self, context, member):
        """Delete a pool member on the OpenDaylight Controller."""
        url = (
            POOLS_URL_PATH + '/' + member['pool_id'] +
            '/' + odl_const.ODL_MEMBERS + "/" + member['id'])
        self.client.sendjson('delete', url, None)

    def create_pool_health_monitor(self, context, health_monitor, pool_id):
        """Create a pool health monitor on the OpenDaylight Controller."""
        url = HEALTHMONITORS_URL_PATH
        self.client.sendjson(
            'post', url, {odl_const.ODL_HEALTHMONITOR: health_monitor})

    def update_pool_health_monitor(self, context, old_health_monitor,
                                   health_monitor, pool_id):
        """Update a pool health monitor on the OpenDaylight Controller."""
        url = HEALTHMONITORS_URL_PATH + "/" + old_health_monitor['id']
        self.client.sendjson(
            'put', url, {odl_const.ODL_HEALTHMONITOR: health_monitor})

    def delete_pool_health_monitor(self, context, health_monitor, pool_id):
        """Delete a pool health monitor on the OpenDaylight Controller."""
        url = HEALTHMONITORS_URL_PATH + "/" + health_monitor['id']
        self.client.sendjson('delete', url, None)

    def stats(self, context, pool_id):
        """Retrieve pool statistics from the OpenDaylight Controller."""
        pass
