# Copyright (c) 2015-2016 OpenStack Foundation
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


import fixtures
import mock

from neutron.tests import base
from neutron_lib.callbacks import registry
from neutron_lib import fixture as nl_fixture
from oslo_config import cfg
from oslo_config import fixture as config_fixture

from networking_odl.common import odl_features
from networking_odl.journal import full_sync
from networking_odl.journal import journal
from networking_odl.journal import periodic_task
from networking_odl.ml2 import pseudo_agentdb_binding


class DietTestCase(base.DietTestCase):

    def patch(self, target, name, *args, **kwargs):
        context = mock.patch.object(target, name, *args, **kwargs)
        patch = context.start()
        self.addCleanup(context.stop)
        return patch


class OpenDaylightRestClientFixture(fixtures.Fixture):
    # Set URL/user/pass so init doesn't throw a cfg required error.
    # They are not used in these tests since requests.request is overwritten.
    def _setUp(self):
        super(OpenDaylightRestClientFixture, self)._setUp()
        self.cfg = self.useFixture(config_fixture.Config())
        mock.patch('requests.sessions.Session.request').start()
        self.cfg.config(url='http://localhost:8080/controller/nb/v2/neutron',
                        group='ml2_odl')
        self.cfg.config(username='someuser', group='ml2_odl')
        self.cfg.config(password='somepass', group='ml2_odl')
        self.cfg.config(port_binding_controller='legacy-port-binding',
                        group='ml2_odl')


class OpenDaylightRestClientGlobalFixture(fixtures.Fixture):
    def __init__(self, global_client):
        super(OpenDaylightRestClientGlobalFixture, self).__init__()
        self._global_client = global_client

    def _setUp(self):
        super(OpenDaylightRestClientGlobalFixture, self)._setUp()
        mock.patch.object(self._global_client, 'get_client').start()


class OpenDaylightFeaturesFixture(fixtures.Fixture):
    def _setUp(self):
        super(OpenDaylightFeaturesFixture, self)._setUp()
        self.cfg = self.useFixture(config_fixture.Config())
        if cfg.CONF.ml2_odl.url is None:
            self.cfg.config(url='http://127.0.0.1:9999', group='ml2_odl')
        if cfg.CONF.ml2_odl.username is None:
            self.cfg.config(username='someuser', group='ml2_odl')
        if cfg.CONF.ml2_odl.password is None:
            self.cfg.config(password='somepass', group='ml2_odl')
        # make sure _fetch_features is not called, it'll block the main thread
        self.cfg.config(odl_features_json='{"features": {"feature": []}}',
                        group='ml2_odl')
        odl_features.init()
        self.addCleanup(odl_features.deinit)


class OpenDaylightJournalThreadFixture(fixtures.Fixture):
    def _setUp(self):
        super(OpenDaylightJournalThreadFixture, self)._setUp()
        self.journal_thread_mock = mock.patch.object(
            journal.OpenDaylightJournalThread, 'start')
        self.journal_thread_mock.start()
        self.pidfile_fixture = self.useFixture(JournalWorkerPidFileFixture())

    def remock_atexit(self):
        self.pidfile_fixture.atexit_mock.stop()
        return self.pidfile_fixture.atexit_mock.start()


class JournalWorkerPidFileFixture(fixtures.Fixture):
    def _setUp(self):
        super(JournalWorkerPidFileFixture, self)._setUp()
        # Every pidfile that is created for the JournalPeriodicProcessor
        # worker registers an operation to clean it when the interpreter
        # is about to exit. Tests each have a temporary directory where
        # they work, this directory is deleted after each test. That means
        # that by the time atexit is called the pidfile does not exist anymore
        # and therefore fails with an error. This avoids this problem.
        self.atexit_mock = mock.patch(
            'networking_odl.journal.worker.atexit.register'
        )
        self.atexit_mock.start()


class OpenDaylightPeriodicTaskFixture(fixtures.Fixture):
    def _setUp(self):
        super(OpenDaylightPeriodicTaskFixture, self)._setUp()
        self.task_start_mock = mock.patch.object(
            periodic_task.PeriodicTask, 'start')
        self.task_start_mock.start()


class OpenDaylightPseudoAgentPrePopulateFixture(
        nl_fixture.CallbackRegistryFixture):
    def _setUp(self):
        super(OpenDaylightPseudoAgentPrePopulateFixture, self)._setUp()
        mock.patch.object(
            pseudo_agentdb_binding.PseudoAgentDBBindingPrePopulate,
            'before_port_binding').start()

    # NOTE(yamahata): work around
    # CallbackRegistryFixture._restore causes stopping unstarted patcher
    # bacause some of base classes neutron test cases issue stop_all()
    # with tearDown method
    def _restore(self):
        registry._CALLBACK_MANAGER = self._orig_manager
        if mock.mock._is_started(self.patcher):
            # this may cause RuntimeError('stop called on unstarted patcher')
            # due to stop_all called by base test cases
            self.patcher.stop()


class OpenDaylightFullSyncFixture(fixtures.Fixture):
    def _setUp(self):
        super(OpenDaylightFullSyncFixture, self)._setUp()
        self.addCleanup(full_sync.FULL_SYNC_RESOURCES.clear)
