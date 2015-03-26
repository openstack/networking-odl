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

from neutron.common import log as call_log
from neutron_lbaas.drivers import driver_base

from networking_odl.common import client as odl_client
from networking_odl.common import config  # noqa

LOG = logging.getLogger(__name__)


class OpenDaylightLbaasDriverV2(driver_base.LoadBalancerBaseDriver):

    """OpenDaylight LBaaS Driver for the V2 API

    This code is the backend implementation for the OpenDaylight
    LBaaS V1 driver for Openstack Neutron.
    """

    def __init__(self, plugin):
        LOG.debug("Initializing OpenDaylight LBaaS driver")
        self.plugin = plugin
        self.client = odl_client.OpenDaylightRestClient(
            cfg.CONF.ml2_odl.url,
            cfg.CONF.ml2_odl.username,
            cfg.CONF.ml2_odl.password,
            cfg.CONF.ml2_odl.timeout
        )


class ODLLoadBalancerManager(driver_base.BaseLoadBalancerManager):

    @call_log.log
    def create(self, context, lb):
        pass

    @call_log.log
    def update(self, context, old_lb, lb):
        pass

    @call_log.log
    def delete(self, context, lb):
        pass

    @call_log.log
    def refresh(self, context, lb):
        pass

    @call_log.log
    def stats(self, context, lb):
        pass


class ODLListenerManager(driver_base.BaseListenerManager):

    @call_log.log
    def create(self, context, listener):
        pass

    @call_log.log
    def update(self, context, old_listener, listener):
        pass

    @call_log.log
    def delete(self, context, listener):
        pass


class ODLPoolManager(driver_base.BasePoolManager):

    @call_log.log
    def create(self, context, pool):
        pass

    @call_log.log
    def update(self, context, old_pool, pool):
        pass

    @call_log.log
    def delete(self, context, listener):
        pass


class ODLMemberManager(driver_base.BaseMemberManager):

    @call_log.log
    def create(self, context, member):
        pass

    @call_log.log
    def update(self, context, old_member, member):
        pass

    @call_log.log
    def delete(self, context, member):
        pass


class ODLHealthMonitorManager(driver_base.BaseHealthMonitorManager):

    @call_log.log
    def create(self, context, hm):
        pass

    @call_log.log
    def update(self, context, old_hm, hm):
        pass

    @call_log.log
    def delete(self, context, hm):
        pass
