# Copyright (c) 2013-2014 OpenStack Foundation
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

from networking_odl.common import callback
from networking_odl.common import constants as odl_const
from networking_odl.ml2.mech_driver import OpenDaylightDriver

import mock
import testscenarios
import testtools

from neutron.callbacks import events
from neutron.callbacks import resources


FAKE_ID = 'fakeid'


class ODLCallbackTestCase(testscenarios.WithScenarios, testtools.TestCase):
    odl_client = OpenDaylightDriver()
    scenarios = [
        ('after', {
            'sgh': callback.OdlSecurityGroupsHandler(odl_client,
                                                     "AFTER")}),
        ('precommit', {
            'sgh': callback.OdlSecurityGroupsHandler(odl_client,
                                                     "PRECOMMIT")}),
    ]

    def setUp(self):
        super(ODLCallbackTestCase, self).setUp()

    @mock.patch.object(OpenDaylightDriver, 'sync_from_callback')
    def test_callback_sg_create(self, sfc):
        context = mock.Mock()
        sg = mock.Mock()
        default_sg = mock.Mock()
        kwargs = {
            'context': context,
            'security_group': sg,
            'security_groups': odl_const.ODL_SGS,
            'is_default': default_sg,
        }
        self.sgh.sg_callback(resources.SECURITY_GROUP,
                             events.AFTER_CREATE,
                             "trigger",
                             **kwargs)

        sfc.assert_called_with(odl_const.ODL_CREATE,
                               'security-groups',
                               None, {'security_group': sg})

    @mock.patch.object(OpenDaylightDriver, 'sync_from_callback')
    def test_callback_sg_update(self, sfc):
        context = mock.Mock()
        sg = mock.Mock()
        kwargs = {
            'context': context,
            'security_group_id': FAKE_ID,
            'security_group': sg,
            'security_groups': odl_const.ODL_SGS,
        }
        self.sgh.sg_callback(resources.SECURITY_GROUP,
                             events.AFTER_UPDATE,
                             "trigger",
                             **kwargs)

        sfc.assert_called_with(odl_const.ODL_UPDATE,
                               'security-groups',
                               FAKE_ID, {'security_group': sg})

    @mock.patch.object(OpenDaylightDriver, 'sync_from_callback')
    def test_callback_sg_delete(self, sfc):
        context = mock.Mock()
        sg = mock.Mock()
        kwargs = {
            'context': context,
            'security_group_id': FAKE_ID,
            'security_group': sg,
            'security_groups': odl_const.ODL_SGS,
        }
        self.sgh.sg_callback(resources.SECURITY_GROUP,
                             events.AFTER_DELETE,
                             "trigger",
                             **kwargs)

        sfc.assert_called_with(odl_const.ODL_DELETE,
                               'security-groups',
                               FAKE_ID, {'security_group': sg})

    @mock.patch.object(OpenDaylightDriver, 'sync_from_callback')
    def test_callback_sg_rules_create(self, sfc):
        context = mock.Mock()
        security_group_rule = mock.Mock()
        kwargs = {
            'context': context,
            'security_group_rule': security_group_rule,
            'security_group_rules': odl_const.ODL_SG_RULES,
        }
        self.sgh.sg_callback(resources.SECURITY_GROUP_RULE,
                             events.AFTER_CREATE,
                             "trigger",
                             **kwargs)

        sfc.assert_called_with(odl_const.ODL_CREATE,
                               'security-group-rules',
                               None,
                               {'security_group_rule': security_group_rule})

    @mock.patch.object(OpenDaylightDriver, 'sync_from_callback')
    def test_callback_sg_rules_delete(self, sfc):
        context = mock.Mock()
        kwargs = {
            'context': context,
            'security_group_rule_id': FAKE_ID,
            'security_group_rules': odl_const.ODL_SG_RULES,
        }
        self.sgh.sg_callback(resources.SECURITY_GROUP_RULE,
                             events.AFTER_DELETE,
                             "trigger",
                             **kwargs)

        sfc.assert_called_with(odl_const.ODL_DELETE,
                               'security-group-rules',
                               FAKE_ID, None)
