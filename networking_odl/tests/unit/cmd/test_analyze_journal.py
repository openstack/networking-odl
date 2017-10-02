# Copyright (c) 2017 Red Hat, Inc.
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

import contextlib
import random
import string

import fixtures
import mock

from six import StringIO

from networking_odl.cmd import analyze_journal
from networking_odl.journal import journal
from networking_odl.tests import base


def _random_string():
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters)
                   for _ in range(random.randint(1, 10)))


def _generate_log_entry(log_type=None, entry_id=None):
    entry = mock.Mock()
    entry.seqnum = entry_id if entry_id else _random_string()
    entry.operation = _random_string()
    entry.object_type = _random_string()
    entry.object_uuid = _random_string()

    logger = fixtures.FakeLogger()
    with logger:
        journal._log_entry(log_type if log_type else _random_string(), entry)

    return entry, "noise %s noise" % logger.output


class TestAnalyzeJournal(base.DietTestCase):
    def setUp(self):
        super(TestAnalyzeJournal, self).setUp()
        self.output = StringIO()

    def _assert_nothing_printed(self):
        self.assertEqual('', self.output.getvalue())

    def _assert_something_printed(self, expected=None):
        self.assertNotEqual('', self.output.getvalue())
        if expected:
            self.assertIn(str(expected), self.output.getvalue())

    def test_setup_conf_no_args(self):
        conf = analyze_journal.setup_conf(self.output, [])
        self.assertIsNotNone(conf)
        self._assert_nothing_printed()

    def test_setup_conf_h_flag(self):
        self.assertRaises(
            SystemExit, analyze_journal.setup_conf, self.output, ['-h'])
        self._assert_something_printed()

    def test_setup_conf_help_flag(self):
        self.assertRaises(
            SystemExit, analyze_journal.setup_conf, self.output, ['--help'])
        self._assert_something_printed()

    def test_setup_conf_file(self):
        file_name = _random_string()
        conf = analyze_journal.setup_conf(self.output, ['--file', file_name])
        self.assertEqual(file_name, conf.file)

    def test_setup_conf_slowest(self):
        slowest = random.randint(1, 10000)
        conf = analyze_journal.setup_conf(
            self.output, ['--slowest', str(slowest)])
        self.assertEqual(slowest, conf.slowest)

    def test_setup_conf_slowest_zero(self):
        self.assertRaises(SystemExit, analyze_journal.setup_conf,
                          self.output, ['--slowest', '0'])
        self._assert_nothing_printed()

    def test_parse_log_no_matched_content(self):
        self.assertEqual({}, analyze_journal.parse_log([]))
        self.assertEqual({}, analyze_journal.parse_log(['dummy']))

    def _test_parse_log_entry(self, recorded=False, completed=False):
        content = []
        entry_id = _random_string()
        entry = None

        if recorded:
            entry, log = _generate_log_entry(log_type=journal.LOG_RECORDED,
                                             entry_id=entry_id)
            content.append(log)

        if completed:
            centry, log = _generate_log_entry(log_type=journal.LOG_COMPLETED,
                                              entry_id=entry_id)
            entry = centry if entry is None else entry
            content.append(log)

        entries = analyze_journal.parse_log(content)
        actual_entry = entries[entry_id]
        self.assertEqual(entry.operation, actual_entry['op'])
        self.assertEqual(entry.object_type, actual_entry['obj_type'])
        self.assertEqual(entry.object_uuid, actual_entry['obj_id'])

        if recorded:
            self.assertGreater(actual_entry[journal.LOG_RECORDED], 0)

        if completed:
            self.assertGreater(actual_entry[journal.LOG_COMPLETED], 0)

    def test_parse_log_entry_recorded(self):
        self._test_parse_log_entry(recorded=True)

    def test_parse_log_entry_completed(self):
        self._test_parse_log_entry(completed=True)

    def test_parse_log_entry_recorded_and_completed(self):
        self._test_parse_log_entry(recorded=True, completed=True)

    def test_analyze_entries_no_records(self):
        self.assertEqual([], analyze_journal.analyze_entries({}))

    def _generate_random_entry(self):
        return dict([(k, _random_string()) for k in analyze_journal.LOG_KEYS])

    def _entry_for_analyze_entries(self, recorded=False, completed=False):
        entry = self._generate_random_entry()

        if recorded:
            entry[journal.LOG_RECORDED] = random.uniform(1, 10)

        if completed:
            entry[journal.LOG_COMPLETED] = random.uniform(10, 20)

        return entry

    def test_analyze_entries_no_completed_time(self):
        entry = self._entry_for_analyze_entries(recorded=True)
        entries = {entry['entry_id']: entry}
        self.assertEqual([], analyze_journal.analyze_entries(entries))

    def test_analyze_entries_no_recorded_time(self):
        entry = self._entry_for_analyze_entries(completed=True)
        entries = {entry['entry_id']: entry}
        self.assertEqual([], analyze_journal.analyze_entries(entries))

    def test_analyze_entries(self):
        entry = self._entry_for_analyze_entries(recorded=True, completed=True)
        entry_only_recorded = self._entry_for_analyze_entries(recorded=True)
        entry_only_completed = self._entry_for_analyze_entries(completed=True)

        entries = {e['entry_id']: e for e in
                   (entry, entry_only_recorded, entry_only_completed)}
        entries_stats = analyze_journal.analyze_entries(entries)

        expected_time = (entry[journal.LOG_COMPLETED] -
                         entry[journal.LOG_RECORDED])
        expected_entry = analyze_journal.EntryStats(
            entry_id=entry['entry_id'], time=expected_time, op=entry['op'],
            obj_type=entry['obj_type'], obj_id=entry['obj_id'])
        self.assertIn(expected_entry, entries_stats)

    def _assert_percentile_printed(self, entries_stats, percentile):
        expected_percentile_format = "%sth percentile: %s"
        percentile_index = int(len(entries_stats) * (percentile / 100.0))
        entry = entries_stats[percentile_index]

        self._assert_something_printed(expected_percentile_format %
                                       (percentile, entry.time))

    def test_print_stats(self):
        entries_stats = []
        entries_count = 10
        slowest = random.randint(1, int(entries_count / 2))
        for i in range(entries_count):
            entry = self._generate_random_entry()
            entries_stats.append(
                analyze_journal.EntryStats(
                    entry_id=entry['entry_id'], time=i, op=entry['op'],
                    obj_type=entry['obj_type'], obj_id=entry['obj_id']))

        analyze_journal.print_stats(self.output, slowest, entries_stats)

        total_time = (entries_count * (entries_count - 1)) / 2
        avg_time = total_time / entries_count
        self._assert_something_printed(avg_time)

        self._assert_something_printed(slowest)
        self._assert_percentile_printed(entries_stats, 90)
        self._assert_percentile_printed(entries_stats, 99)
        self._assert_percentile_printed(entries_stats, 99.9)

        expected = ''
        for i in reversed(range(entries_count - slowest, entries_count)):
            entry = entries_stats[i]
            expected += '\n'
            expected += (analyze_journal.ENTRY_LOG_TEMPLATE %
                         (entry.entry_id, entry.time, entry.op, entry.obj_type,
                          entry.obj_id))
            self._assert_something_printed(expected)

    @contextlib.contextmanager
    def _setup_mocks_for_main(self, content):
        with mock.patch.object(analyze_journal, 'get_content') as mgc, \
                mock.patch.object(analyze_journal, 'setup_conf') as msc:
            m = mock.MagicMock()
            m.__iter__.return_value = content
            mgc().__enter__.return_value = m
            conf = msc()
            conf.slowest = 10
            yield

    def test_main(self):
        entry_id = _random_string()
        _, entry_recorded = _generate_log_entry(journal.LOG_RECORDED, entry_id)
        _, entry_completed = _generate_log_entry(journal.LOG_COMPLETED,
                                                 entry_id)
        with self._setup_mocks_for_main((entry_recorded, entry_completed)):
            rc = analyze_journal.main(self.output)

        self.assertEqual(0, rc)
        self._assert_something_printed(entry_id)

    def test_main_no_entry_stats(self):
        with self._setup_mocks_for_main(('dummy',)):
            rc = analyze_journal.main(self.output)

        self.assertNotEqual(0, rc)
        self._assert_something_printed()
