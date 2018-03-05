# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock

import neutron_lbaas
from neutron_lbaas.drivers import driver_base
from neutron_lbaas.services.loadbalancer import data_models

import networking_odl
from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.journal import journal
from networking_odl.lbaas import lbaasv2_driver_v2 as lb_driver
from networking_odl.tests.unit import base_v2


class OpenDaylightLBaaSBaseTestCase(base_v2.OpenDaylightConfigBase):
    @staticmethod
    def _get_faked_model(obj):
        lb = data_models.LoadBalancer(id='test_lb')
        if obj == 'lbaas/loadbalancer':
            return lb

        pool = data_models.Pool(id='test_pool_id',
                                loadbalancer=lb)
        if obj == 'lbaas/pool':
            return pool

        listener = data_models.Listener(id='test_listener_id',
                                        loadbalancer=lb)
        if obj == 'lbaas/listener':
            return listener

        member = data_models.Member(id='test_member_id',
                                    pool=pool)
        if obj == 'lbaas/member':
            return member

        hm = data_models.HealthMonitor(id='test_health_monitor_id',
                                       pool=pool)

        return hm

    @mock.patch.object(
        networking_odl.journal.journal.OpenDaylightJournalThread,
        'set_sync_event')
    @mock.patch.object(neutron_lbaas.drivers.driver_mixins.BaseManagerMixin,
                       'successful_completion')
    def base_test_operation(self, obj_driver, obj_type, operation, op_const,
                            mock_set_sync_event, mock_successful_completion):
        obj = self._get_faked_model(obj_type)
        getattr(obj_driver, operation)(self.db_context, obj)
        row = db.get_oldest_pending_db_row_with_lock(self.db_context)
        self.assertEqual(operation, row['operation'])
        if obj_type != odl_const.ODL_MEMBER:
            self.assertEqual(("lbaas/%s" % obj_type), row['object_type'])
        else:
            self.assertEqual(journal.MAKE_URL[obj_type](row),
                             ("lbaas/pools/%s/member" % obj.pool.id))


class OpenDaylightLBaaSDriverTestCase(OpenDaylightLBaaSBaseTestCase):
    def _test_operation(self, obj_type, operation, op_const):
        driver = mock.Mock()
        obj_driver = lb_driver.OpenDaylightManager(driver, obj_type)
        self.base_test_operation(self, obj_driver, obj_type,
                                 operation, op_const)


class ODLLoadBalancerManagerTestCase(OpenDaylightLBaaSBaseTestCase):
    def _test_operation(self, operation, op_const):
        driver = mock.Mock()
        obj_type = odl_const.ODL_LOADBALANCER
        obj_driver = lb_driver.ODLLoadBalancerManager(driver)
        self.base_test_operation(obj_driver, obj_type, operation, op_const)

    def test_create_load_balancer(self):
        self._test_operation('create', odl_const.ODL_CREATE)

    def test_update_load_balancer(self):
        self._test_operation('update', odl_const.ODL_UPDATE)

    def test_delete_load_balancer(self):
        self._test_operation('delete', odl_const.ODL_DELETE)

    def test_db_delete_method_load_balancer(self):
        # TODO(mpeterson): implement a proper test. Probably it should test all
        # drivers in a consistent way.
        driver = lb_driver.ODLLoadBalancerManager(mock.Mock())
        self.assertIsInstance(driver.db_delete_method, property)
        self.assertIs(
            driver.db_delete_method,
            driver_base.BaseLoadBalancerManager.db_delete_method)


class ODLListenerManagerTestCase(OpenDaylightLBaaSBaseTestCase):
    def _test_operation(self, operation, op_const):
        driver = mock.Mock()
        obj_type = odl_const.ODL_LISTENER
        obj_driver = lb_driver.ODLListenerManager(driver)
        self.base_test_operation(obj_driver, obj_type, operation, op_const)

    def test_create_listener(self):
        self._test_operation('create', odl_const.ODL_CREATE)

    def test_update_listener(self):
        self._test_operation('update', odl_const.ODL_UPDATE)

    def test_delete_listener(self):
        self._test_operation('delete', odl_const.ODL_DELETE)


class ODLPoolManagerTestCase(OpenDaylightLBaaSBaseTestCase):
    def _test_operation(self, operation, op_const):
        obj_type = odl_const.ODL_POOL
        obj = mock.MagicMock()
        obj_driver = lb_driver.ODLPoolManager(obj)
        self.base_test_operation(obj_driver, obj_type, operation, op_const)

    def test_create_pool(self):
        self._test_operation('create', odl_const.ODL_CREATE)

    def test_update_pool(self):
        self._test_operation('update', odl_const.ODL_UPDATE)

    def test_delete_pool(self):
        self._test_operation('delete', odl_const.ODL_DELETE)


class ODLMemberManagerTestCase(OpenDaylightLBaaSBaseTestCase):
    def _test_operation(self, operation, op_const):
        driver = mock.Mock()
        obj_type = odl_const.ODL_MEMBER
        obj_driver = lb_driver.ODLMemberManager(driver)
        self.base_test_operation(obj_driver, obj_type, operation, op_const)

    def test_create_member(self):
        self._test_operation('create', odl_const.ODL_CREATE)

    def test_update_member(self):
        self._test_operation('update', odl_const.ODL_UPDATE)

    def test_delete_member(self):
        self._test_operation('delete', odl_const.ODL_DELETE)


class ODLHealthMonitorManagerTestCase(OpenDaylightLBaaSBaseTestCase):
    def _test_operation(self, operation, op_const):
        driver = mock.Mock()
        obj_type = odl_const.ODL_HEALTHMONITOR
        obj_driver = lb_driver.ODLHealthMonitorManager(driver)
        self.base_test_operation(obj_driver, obj_type, operation, op_const)

    def test_create_health_monitor(self):
        self._test_operation('create', odl_const.ODL_CREATE)

    def test_update_health_monitor(self):
        self._test_operation('update', odl_const.ODL_UPDATE)

    def test_delete_health_monitor(self):
        self._test_operation('delete', odl_const.ODL_DELETE)
