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
from networking_odl.common import constants as odl_const

LOG = logging.getLogger(__name__)

LBAAS = "lbaas"


class OpenDaylightLbaasDriverV2(driver_base.LoadBalancerBaseDriver):

    @call_log.log
    def __init__(self, plugin):
        LOG.debug("Initializing OpenDaylight LBaaS driver")
        self.plugin = plugin
        self.client = odl_client.OpenDaylightRestClient(
            cfg.CONF.ml2_odl.url,
            cfg.CONF.ml2_odl.username,
            cfg.CONF.ml2_odl.password,
            cfg.CONF.ml2_odl.timeout
        )
        self._loadbalancer = ODLLoadBalancerManager(self.client)
        self._listener = ODLListenerManager(self.client)
        self._pool = ODLPoolManager(self.client)
        self._member = ODLMemberManager(self.client)
        self._healthmonitor = ODLHealthMonitorManager(self.client)


class OpenDaylightManager(object):

    out_of_sync = True
    url_path = ""
    obj_type = ""

    """OpenDaylight LBaaS Driver for the V2 API

    This code is the backend implementation for the OpenDaylight
    LBaaS V1 driver for Openstack Neutron.
    """

    @call_log.log
    def __init__(self, client):
        self.client = client
        self.url_path = LBAAS + self.obj_type

    @call_log.log
    def create(self, context, obj):
        self.client.sendjson('post', self.obj_type, None)

    @call_log.log
    def update(self, context, obj):
        self.client.sendjson('put', self.obj_type + '/' + obj.id, None)

    @call_log.log
    def delete(self, context, obj):
        self.client.sendjson('delete', self.obj_type + '/' + obj.id, None)


class ODLLoadBalancerManager(OpenDaylightManager,
                             driver_base.BaseLoadBalancerManager):

    @call_log.log
    def __init__(self, client):
        self.obj_type = odl_const.ODL_LOADBALANCERS
        super(ODLLoadBalancerManager, self).__init__(client)

    @call_log.log
    def refresh(self, context, lb):
        pass

    @call_log.log
    def stats(self, context, lb):
        pass


class ODLListenerManager(OpenDaylightManager,
                         driver_base.BaseListenerManager):

    @call_log.log
    def __init__(self, client):
        self.obj_type = odl_const.ODL_LISTENERS
        super(ODLListenerManager, self).__init__(client)


class ODLPoolManager(OpenDaylightManager,
                     driver_base.BasePoolManager):

    @call_log.log
    def __init__(self, client):
        self.obj_type = odl_const.ODL_POOLS
        super(ODLPoolManager, self).__init__(client)


class ODLMemberManager(OpenDaylightManager,
                       driver_base.BaseMemberManager):

    @call_log.log
    def __init__(self, client):
        self.obj_type = odl_const.ODL_MEMBERS
        super(ODLMemberManager, self).__init__(client)


class ODLHealthMonitorManager(OpenDaylightManager,
                              driver_base.BaseHealthMonitorManager):

    @call_log.log
    def __init__(self, client):
        self.obj_type = odl_const.ODL_HEALTHMONITORS
        super(ODLHealthMonitorManager, self).__init__(client)
