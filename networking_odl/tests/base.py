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

from oslo_config import cfg

from networking_odl.common import odl_features
from networking_odl.journal import periodic_task
from neutron.tests import base

from networking_odl.journal import journal


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
        mock.patch('requests.sessions.Session.request').start()
        cfg.CONF.set_override('url',
                              'http://localhost:8080'
                              '/controller/nb/v2/neutron', 'ml2_odl')
        cfg.CONF.set_override('username', 'someuser', 'ml2_odl')
        cfg.CONF.set_override('password', 'somepass', 'ml2_odl')
        cfg.CONF.set_override('port_binding_controller',
                              'legacy-port-binding', 'ml2_odl')


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
        if cfg.CONF.ml2_odl.url is None:
            cfg.CONF.set_override('url', 'http://127.0.0.1:9999', 'ml2_odl')
        if cfg.CONF.ml2_odl.username is None:
            cfg.CONF.set_override('username', 'someuser', 'ml2_odl')
        if cfg.CONF.ml2_odl.password is None:
            cfg.CONF.set_override('password', 'somepass', 'ml2_odl')
        # make sure init is not called, it'll block the main thread
        self.mock_odl_features_init = mock.patch.object(
            odl_features, 'init', side_effect=self.fake_init)
        self.mock_odl_features_init.start()
        self.addCleanup(odl_features.deinit)

    @staticmethod
    def fake_init():
        odl_features.feature_set = set()


class OpenDaylightJournalThreadFixture(fixtures.Fixture):
    def _setUp(self):
        super(OpenDaylightJournalThreadFixture, self)._setUp()
        mock.patch.object(journal.OpenDaylightJournalThread,
                          'start').start()


class OpenDaylightPeriodicTaskFixture(fixtures.Fixture):
    def _setUp(self):
        super(OpenDaylightPeriodicTaskFixture, self)._setUp()
        mock.patch.object(periodic_task.PeriodicTask, 'start').start()
