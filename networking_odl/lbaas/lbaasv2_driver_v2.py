#
# Copyright (C) 2017 NEC, Corp.
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

from neutron_lib.plugins import constants as nlib_const
from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from neutron_lbaas.drivers import driver_base
from neutron_lbaas.drivers import driver_mixins

from networking_odl.common import constants as odl_const
from networking_odl.journal import full_sync
from networking_odl.journal import journal

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = logging.getLogger(__name__)

LBAAS_RESOURCES = {
    odl_const.ODL_LOADBALANCER: odl_const.ODL_LOADBALANCERS,
    odl_const.ODL_LISTENER: odl_const.ODL_LISTENERS,
    odl_const.ODL_POOL: odl_const.ODL_POOLS,
    odl_const.ODL_MEMBER: odl_const.ODL_MEMBERS,
    odl_const.ODL_HEALTHMONITOR: odl_const.ODL_HEALTHMONITORS
}


class OpenDaylightLbaasDriverV2(driver_base.LoadBalancerBaseDriver):
    @log_helpers.log_method_call
    def __init__(self, plugin):
        super(OpenDaylightLbaasDriverV2, self).__init__(plugin)
        LOG.debug("Initializing OpenDaylight LBaaS driver")
        self.load_balancer = ODLLoadBalancerManager(self)
        self.listener = ODLListenerManager(self)
        self.pool = ODLPoolManager(self)
        self.member = ODLMemberManager(self)
        self.health_monitor = ODLHealthMonitorManager(self)


class OpenDaylightManager(driver_mixins.BaseManagerMixin):
    """OpenDaylight LBaaS Driver for the V2 API

    This code is the backend implementation for the OpenDaylight
    LBaaS V2 driver for OpenStack Neutron.
    """

    @log_helpers.log_method_call
    def __init__(self, driver, obj_type):
        LOG.debug("Initializing OpenDaylight LBaaS driver")
        super(OpenDaylightManager, self).__init__(driver)
        self.journal = journal.OpenDaylightJournalThread()
        self.obj_type = obj_type
        full_sync.register(nlib_const.LOADBALANCERV2, LBAAS_RESOURCES,
                           self.get_resources)
        self.driver = driver

    def _journal_record(self, context, obj_type, obj_id, operation, obj):
        obj_type = ("lbaas/%s" % obj_type)
        journal.record(context, obj_type, obj_id, operation, obj)
        self.journal.set_sync_event()

    @staticmethod
    def get_resources(context, resource_type):
        plugin = directory.get_plugin(nlib_const.LOADBALANCERV2)
        if resource_type == odl_const.ODL_MEMBER:
            return full_sync.get_resources_require_id(plugin, context,
                                                      plugin.get_pools,
                                                      'get_pool_members')

        obj_getter = getattr(plugin, 'get_%s' % LBAAS_RESOURCES[resource_type])
        return obj_getter(context)

    @log_helpers.log_method_call
    @driver_base.driver_op
    def create(self, context, obj):
        self._journal_record(context, self.obj_type, obj.id,
                             odl_const.ODL_CREATE, obj)

    @log_helpers.log_method_call
    @driver_base.driver_op
    def update(self, context, obj):
        self._journal_record(context, self.obj_type, obj.id,
                             odl_const.ODL_UPDATE, obj)

    @log_helpers.log_method_call
    @driver_base.driver_op
    def delete(self, context, obj):
        self._journal_record(context, self.obj_type, obj.id,
                             odl_const.ODL_DELETE, obj)


class ODLLoadBalancerManager(OpenDaylightManager,
                             driver_base.BaseLoadBalancerManager):

    @log_helpers.log_method_call
    def __init__(self, driver):
        super(ODLLoadBalancerManager, self).__init__(
            driver, odl_const.ODL_LOADBALANCER)

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
        # TODO(rajivk): implement this method
        pass

    # NOTE(mpeterson): workaround for pylint
    # pylint raises false positive of abstract-class-instantiated
    @property
    def db_delete_method(self):
        return driver_base.BaseLoadBalancerManager.db_delete_method


class ODLListenerManager(OpenDaylightManager,
                         driver_base.BaseListenerManager):

    @log_helpers.log_method_call
    def __init__(self, driver):
        super(ODLListenerManager, self).__init__(
            driver, odl_const.ODL_LISTENER)


class ODLPoolManager(OpenDaylightManager,
                     driver_base.BasePoolManager):

    @log_helpers.log_method_call
    def __init__(self, driver):
        super(ODLPoolManager, self).__init__(
            driver, odl_const.ODL_POOL)


class ODLMemberManager(OpenDaylightManager,
                       driver_base.BaseMemberManager):

    @log_helpers.log_method_call
    def __init__(self, driver):
        super(ODLMemberManager, self).__init__(
            driver, odl_const.ODL_MEMBER)

        journal.register_url_builder(odl_const.ODL_MEMBER,
                                     self.lbaas_member_url_builder)

    @staticmethod
    def lbaas_member_url_builder(row):
        return ("lbaas/pools/%s/member" % row.data.pool.id)


class ODLHealthMonitorManager(OpenDaylightManager,
                              driver_base.BaseHealthMonitorManager):

    @log_helpers.log_method_call
    def __init__(self, driver):
        super(ODLHealthMonitorManager, self).__init__(
            driver, odl_const.ODL_HEALTHMONITOR)
