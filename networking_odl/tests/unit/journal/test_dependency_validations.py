#
# Copyright (C) 2016 Intel Corp. Isaku Yamahata <isaku.yamahata@gmail com>
# All Rights Reserved.
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

import mock

from neutron.tests import base

from networking_odl.journal import dependency_validations


class DependencyValidationsTestCase(base.DietTestCase):
    _RESOURCE_DUMMY = 'test_type'

    def setUp(self):
        super(DependencyValidationsTestCase, self).setUp()
        mock_validation_map = mock.patch.dict(
            dependency_validations._VALIDATION_MAP)
        mock_validation_map.start()
        self.addCleanup(mock_validation_map.stop)

    def test_register_validator(self):
        mock_session = mock.Mock()
        mock_validator = mock.Mock(return_value=False)
        mock_row = mock.Mock()
        mock_row.object_type = self._RESOURCE_DUMMY
        dependency_validations.register_validator(self._RESOURCE_DUMMY,
                                                  mock_validator)
        valid = dependency_validations.validate(mock_session, mock_row)
        mock_validator.assert_called_once_with(mock_session, mock_row)
        self.assertFalse(valid)
