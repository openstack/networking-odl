# Copyright (c) 2015 OpenStack Foundation
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

import mock

from neutron.tests import base

from networking_odl.common import cache


class TestCache(base.DietTestCase):

    def test_init_with_callable(self):

        def given_fetch_method():
            pass

        cache.Cache(given_fetch_method)

    def test_init_without_callable(self):
        self.assertRaises(TypeError, lambda: cache.Cache(object()))

    def test_fecth_once(self):
        value = 'value'

        given_fetch_method = mock.Mock(return_value=iter([('key', value)]))
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        result = given_cache.fetch('key', 60.0)

        # Result is returned
        self.assertIs(value, result)

        # Then fetch method is called once
        given_fetch_method.assert_called_once_with(('key',))

    def test_fecth_with_no_result(self):
        given_fetch_method = mock.Mock(return_value=iter([]))
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        try:
            given_cache.fetch('key', 60.0)
        except cache.CacheFetchError as error:
            given_fetch_method.assert_called_once_with(('key',))
            self.assertRaises(KeyError, error.reraise_cause)
        else:
            self.fail('Expecting CacheFetchError to be raised.')

    @mock.patch.object(cache, 'LOG')
    def test_fecth_with_failure(self, logger):
        # pylint: disable=unused-argument

        given_error = RuntimeError("It doesn't work like this!")

        def failing_function(keys):
            raise given_error

        given_fetch_method = mock.Mock(side_effect=failing_function)
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        try:
            given_cache.fetch('key', 60.0)
        except cache.CacheFetchError as error:
            given_fetch_method.assert_called_once_with(('key',))
            self.assertRaises(RuntimeError, error.reraise_cause)
        else:
            self.fail('Expecting CacheFetchError to be raised.')
        logger.warning.assert_called_once_with(
            'Error fetching values for keys: %r', "'key'",
            exc_info=(type(given_error), given_error, mock.ANY))

    def test_fecth_again_after_clear(self):
        value1 = 'value1'
        value2 = 'value2'
        given_fetch_method = mock.Mock(
            side_effect=[iter([('key', value1)]),
                         iter([('key', value2)])])
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        result1 = given_cache.fetch('key', 60.0)

        # When cache is cleared
        given_cache.clear()

        # When value with same key is fetched again
        result2 = given_cache.fetch('key', 0.0)

        # Then first result is returned
        self.assertIs(value1, result1)

        # Then fetch method is called twice
        self.assertEqual(
            [mock.call(('key',)), mock.call(('key',))],
            given_fetch_method.mock_calls)

        # Then second result is returned
        self.assertIs(value2, result2)

    def test_fecth_again_before_timeout(self):
        value1 = 'value1'
        value2 = 'value2'
        given_fetch_method = mock.Mock(
            side_effect=[iter([('key', value1)]),
                         iter([('key', value2)])])
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        result1 = given_cache.fetch('key', 1.0)

        # When value with same key is fetched again and cached entry is not
        # expired
        result2 = given_cache.fetch('key', 0.0)

        # First result is returned
        self.assertIs(value1, result1)

        # Then fetch method is called once
        given_fetch_method.assert_called_once_with(('key',))

        # Then first result is returned twice
        self.assertIs(value1, result2)

    def test_fecth_again_after_timeout(self):
        value1 = 'value1'
        value2 = 'value2'
        given_fetch_method = mock.Mock(
            side_effect=[iter([('key', value1)]),
                         iter([('key', value2)])])
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        result1 = given_cache.fetch('key', 0.0)

        # When value with same key is fetched again and cached entry is
        # expired
        result2 = given_cache.fetch('key', 0.0)

        # Then first result is returned
        self.assertIs(value1, result1)

        # Then fetch method is called twice
        self.assertEqual(
            [mock.call(('key',)), mock.call(('key',))],
            given_fetch_method.mock_calls)

        # Then second result is returned
        self.assertIs(value2, result2)

    def test_fecth_two_values_yielding_both_before_timeout(self):
        value1 = 'value1'
        value2 = 'value2'
        given_fetch_method = mock.Mock(
            return_value=iter([('key1', value1),
                               ('key2', value2)]))
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        result1 = given_cache.fetch('key1', 60.0)

        # When value with another key is fetched and cached entry is not
        # expired
        result2 = given_cache.fetch('key2', 60.0)

        # Then first result is returned
        self.assertIs(value1, result1)

        # Then fetch method is called once
        given_fetch_method.assert_called_once_with(('key1',))

        # Then second result is returned
        self.assertIs(value2, result2)

    def test_fecth_two_values_yielding_both_after_timeout(self):
        value1 = 'value1'
        value2 = 'value2'
        given_fetch_method = mock.Mock(
            return_value=[('key1', value1), ('key2', value2)])
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        result1 = given_cache.fetch('key1', 0.0)

        # When value with another key is fetched and cached entry is
        # expired
        result2 = given_cache.fetch('key2', 0.0)

        # Then first result is returned
        self.assertIs(value1, result1)

        # Then fetch method is called twice
        self.assertEqual(
            [mock.call(('key1',)), mock.call(('key2',))],
            given_fetch_method.mock_calls)

        # Then second result is returned
        self.assertIs(value2, result2)

    def test_fecth_all_with_multiple_entries(self):
        given_fetch_method = mock.Mock(
            return_value=iter([('key', 'value1'),
                               ('key', 'value2')]))
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        results = list(given_cache.fetch_all(['key'], 0.0))

        # Then fetch method is once
        given_fetch_method.assert_called_once_with(('key',))

        # Then both results are yield in the right order
        self.assertEqual([('key', 'value1'), ('key', 'value2')], results)

    def test_fecth_all_with_repeated_entries(self):
        entry = ('key', 'value')
        given_fetch_method = mock.Mock(
            return_value=iter([entry, entry, entry]))
        given_cache = cache.Cache(given_fetch_method)

        # When value with key is fetched
        results = list(given_cache.fetch_all(['key'], 0.0))

        # Then fetch method is once
        given_fetch_method.assert_called_once_with(('key',))

        # Then results are yield in the right order
        self.assertEqual([entry, entry, entry], results)
