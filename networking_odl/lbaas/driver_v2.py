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
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from neutron_lbaas.drivers import driver_base
from neutron_lbaas.drivers import driver_mixins

from networking_odl.common import client as odl_client
from networking_odl.common import constants as odl_const

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = logging.getLogger(__name__)

LBAAS = "lbaas"


class OpenDaylightLbaasDriverV2(driver_base.LoadBalancerBaseDriver):

    @log_helpers.log_method_call
    def __init__(self, plugin):
        LOG.debug("Initializing OpenDaylight LBaaS driver")
        self.plugin = plugin
        self.client = odl_client.OpenDaylightRestClient.create_client()
        self.load_balancer = ODLLoadBalancerManager(self, self.client)
        self.listener = ODLListenerManager(self, self.client)
        self.pool = ODLPoolManager(self, self.client)
        self.member = ODLMemberManager(self, self.client)
        self.health_monitor = ODLHealthMonitorManager(self, self.client)


class OpenDaylightManager(driver_mixins.BaseManagerMixin):

    out_of_sync = True
    url_path = ""
    obj_type = ""
    obj_name = ""

    """OpenDaylight LBaaS Driver for the V2 API

    This code is the backend implementation for the OpenDaylight
    LBaaS V2 driver for OpenStack Neutron.
    """

    @log_helpers.log_method_call
    def __init__(self, driver, client, obj_type):
        super(OpenDaylightManager, self).__init__(driver)
        self.client = client
        self.obj_type = obj_type
        self.url_path = LBAAS + '/' + obj_type
        self.obj_name = obj_type[:-1]

    @log_helpers.log_method_call
    @driver_base.driver_op
    def create(self, context, obj):
        self.client.sendjson('post', self.url_path,
                             {self.obj_name: obj.to_api_dict()})

    @log_helpers.log_method_call
    @driver_base.driver_op
    def update(self, context, obj):
        self.client.sendjson('put', self.url_path + '/' + obj.id,
                             {self.obj_name: obj.to_api_dict()})

    @log_helpers.log_method_call
    @driver_base.driver_op
    def delete(self, context, obj):
        self.client.sendjson('delete', self.url_path + '/' + obj.id, None)


class ODLLoadBalancerManager(OpenDaylightManager,
                             driver_base.BaseLoadBalancerManager):

    @log_helpers.log_method_call
    def __init__(self, driver, client):
        super(ODLLoadBalancerManager, self).__init__(
            driver, client, odl_const.ODL_LOADBALANCERS)

    @log_helpers.log_method_call
    @driver_base.driver_op
    def refresh(self, context, lb):
        # TODO(lijingjing): implement this method
        # This is intended to trigger the backend to check and repair
        # the state of this load balancer and all of its dependent objects
        pass

    @log_helpers.log_method_call
    @driver_base.driver_op
    def stats(self, context, lb):
        # TODO(lijingjing): implement this method
        pass

    # NOTE(yamahata): workaround for pylint
    # pylint raise false positive of abstract-class-instantiated.
    # method resolution order is as follows and db_delete_method is resolved
    # by BaseLoadBalancerManager. However pylint complains as this
    # class is still abstract class
    # mro:
    # ODLLoadBalancerManager
    # OpenDaylightManager
    # neutron_lbaas.drivers.driver_base.BaseLoadBalancerManager
    # neutron_lbaas.drivers.driver_mixins.BaseRefreshMixin
    # neutron_lbaas.drivers.driver_mixins.BaseStatsMixin
    # neutron_lbaas.drivers.driver_mixins.BaseManagerMixin
    # __builtin__.object
    @property
    def db_delete_method(self):
        return driver_base.BaseLoadBalancerManager.db_delete_method


class ODLListenerManager(OpenDaylightManager,
                         driver_base.BaseListenerManager):

    @log_helpers.log_method_call
    def __init__(self, driver, client):
        super(ODLListenerManager, self).__init__(
            driver, client, odl_const.ODL_LISTENERS)


class ODLPoolManager(OpenDaylightManager,
                     driver_base.BasePoolManager):

    @log_helpers.log_method_call
    def __init__(self, driver, client):
        super(ODLPoolManager, self).__init__(
            driver, client, odl_const.ODL_POOLS)


class ODLMemberManager(OpenDaylightManager,
                       driver_base.BaseMemberManager):

    # NOTE:It is for lbaas v2 api but using v1 mechanism of networking-odl.

    @log_helpers.log_method_call
    def __init__(self, driver, client):
        super(ODLMemberManager, self).__init__(
            driver, client, odl_const.ODL_MEMBERS)

    @log_helpers.log_method_call
    @driver_base.driver_op
    def create(self, context, obj):
        self.client.sendjson('post', self._member_url(obj),
                             {self.obj_name: obj.to_api_dict()})

    @log_helpers.log_method_call
    @driver_base.driver_op
    def update(self, context, obj):
        self.client.sendjson('put', self._member_url(obj) + '/' + obj.id,
                             {self.obj_name: obj.to_api_dict()})

    @log_helpers.log_method_call
    @driver_base.driver_op
    def delete(self, context, obj):
        self.client.sendjson('delete',
                             self._member_url(obj) + '/' + obj.id, None)

    def _member_url(self, obj):
        return (LBAAS + '/' + odl_const.ODL_POOLS + '/' + obj.pool_id + '/' +
                odl_const.ODL_MEMBERS)


class ODLHealthMonitorManager(OpenDaylightManager,
                              driver_base.BaseHealthMonitorManager):

    @log_helpers.log_method_call
    def __init__(self, driver, client):
        super(ODLHealthMonitorManager, self).__init__(
            driver, client, odl_const.ODL_HEALTHMONITORS)
