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
import testtools

from neutron.callbacks import events
from neutron.callbacks import resources


FAKE_ID = 'fakeid'


class ODLCallbackTestCase(testtools.TestCase):
    odl_driver = OpenDaylightDriver()
    sgh = callback.OdlSecurityGroupsHandler(odl_driver)

    def setUp(self):
        super(ODLCallbackTestCase, self).setUp()

    @mock.patch.object(OpenDaylightDriver, 'sync_from_callback')
    def _test_callback_for_sg(self, event, op, sg, sg_id, sfc):
        self.sgh.sg_callback(resources.SECURITY_GROUP,
                             event,
                             None,
                             security_group=sg,
                             security_group_id=sg_id)

        expected_dict = ({resources.SECURITY_GROUP: sg}
                         if sg is not None else None)
        sfc.assert_called_with(
            op, callback._RESOURCE_MAPPING[resources.SECURITY_GROUP], sg_id,
            expected_dict)

    def test_callback_sg_create(self):
        self._test_callback_for_sg(events.AFTER_CREATE, odl_const.ODL_CREATE,
                                   mock.Mock(), None)

    def test_callback_sg_update(self):
        self._test_callback_for_sg(events.AFTER_UPDATE, odl_const.ODL_UPDATE,
                                   mock.Mock(), FAKE_ID)

    def test_callback_sg_delete(self):
        self._test_callback_for_sg(events.AFTER_DELETE, odl_const.ODL_DELETE,
                                   None, FAKE_ID)

    @mock.patch.object(OpenDaylightDriver, 'sync_from_callback')
    def _test_callback_for_sg_rules(self, event, op, sg_rule, sg_rule_id, sfc):
        self.sgh.sg_callback(resources.SECURITY_GROUP_RULE,
                             event,
                             None,
                             security_group_rule=sg_rule,
                             security_group_rule_id=sg_rule_id)

        expected_dict = ({resources.SECURITY_GROUP_RULE: sg_rule}
                         if sg_rule is not None else None)
        sfc.assert_called_with(
            op, callback._RESOURCE_MAPPING[resources.SECURITY_GROUP_RULE],
            sg_rule_id, expected_dict)

    def test_callback_sg_rules_create(self):
        self._test_callback_for_sg_rules(
            events.AFTER_CREATE, odl_const.ODL_CREATE, mock.Mock(), None)

    def test_callback_sg_rules_delete(self):
        self._test_callback_for_sg_rules(
            events.AFTER_DELETE, odl_const.ODL_DELETE, None, FAKE_ID)
