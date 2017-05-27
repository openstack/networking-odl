# Copyright (c) 2017 OpenStack Foundation
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

from networking_odl.common import postcommit
from neutron.tests import base


class BaseTest(object):
    def create_resource1_postcommit(self):
        pass

    update_resource1_postcommit = create_resource1_postcommit
    delete_resource1_postcommit = create_resource1_postcommit
    update_resource2_postcommit = create_resource1_postcommit
    delete_resource2_postcommit = create_resource1_postcommit
    create_resource2_postcommit = create_resource1_postcommit


class TestPostCommit(base.DietTestCase):
    def _get_class(self, *args):
        @postcommit.add_postcommit(*args)
        class TestClass(BaseTest):
            pass

        return TestClass

    def _get_methods_name(self, resources):
        ops = ['create', 'update', 'delete']
        m_names = [op + '_' + resource + '_postcommit' for op in ops
                   for resource in resources]

        return m_names

    def test_with_one_resource(self):
        cls = self._get_class('resource1')
        m_names = self._get_methods_name(['resource1'])
        for m_name in m_names:
            self.assertEqual(m_name, getattr(cls, m_name).__name__)

    def test_with_two_resource(self):
        cls = self._get_class('resource1', 'resource2')
        m_names = self._get_methods_name(['resource1', 'resource2'])
        for m_name in m_names:
            self.assertEqual(m_name, getattr(cls, m_name).__name__)

    def test_with_two_resource_create_defined_for_one(self):
        m_names = self._get_methods_name(['resource1', 'resource2'])

        @postcommit.add_postcommit('resource1', 'resource2')
        class TestClass(BaseTest):
            def create_resource1_postcommit(self):
                pass

            create_resource1_postcommit.__name__ = 'test_method'

        for m_name in m_names[1:]:
            self.assertEqual(m_name, getattr(TestClass, m_name).__name__)

        self.assertEqual('test_method',
                         getattr(TestClass, m_names[0]).__name__)
