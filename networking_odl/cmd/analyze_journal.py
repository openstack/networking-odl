#!/usr/bin/env python

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


"""
Command line script to analyze journal entry processing time based on logs.
By default the input is read through pipe, unless a log file is specified.

Examples:
    Analyzing devstack's Neutron log:
        journalctl -u devstack@q-svc | python analyze_journal.py

    Analyzing an arbitrary log file:
        python analyze_journal.py --file /path/to/file.log
"""

import collections
import re
import sys

import six

from oslo_config import cfg

from networking_odl._i18n import _
from networking_odl.journal import journal

COMMAND_LINE_OPTIONS = [
    cfg.StrOpt('file', default=None,
               help=_("Log file to analyze.")),
    cfg.IntOpt('slowest', min=1, default=10,
               help=_("Prints the N slowest entries (10 by default).")),
]

# This regex will match any replacement key in the log message and extract
# the key name.
KEY_MATCHER = re.compile(r'\%\((\S+)\)s')
LOG_KEYS = KEY_MATCHER.findall(journal.LOG_ENTRY_TEMPLATE)
KEY_TEMP_PATTERN = 'KEYPATTERN'
LOG_MATCHER = re.compile(
    re.sub(KEY_TEMP_PATTERN, r'(\S+)', re.escape(
        KEY_MATCHER.sub(KEY_TEMP_PATTERN, journal.LOG_ENTRY_TEMPLATE))))
ENTRY_LOG_TEMPLATE = ' * Entry id: %s, processing time: %.3fs; %s %s %s'

EntryStats = collections.namedtuple(
    'EntryStats', 'entry_id time op obj_type obj_id')


def setup_conf(output, args):
    """setup cmdline options."""

    if any(flag in args for flag in ('-h', '--help')):
        six.print_(__doc__, file=output)

    conf = cfg.ConfigOpts()
    conf.register_cli_opts(COMMAND_LINE_OPTIONS)
    conf(args=args)
    return conf


def parse_log(content):
    entries = {}
    for line in content:
        matched = LOG_MATCHER.search(line)
        if matched is None:
            continue

        entry_log = dict(zip(LOG_KEYS, matched.groups()))
        entry_id = entry_log['entry_id']
        entry = entries.get(entry_id, entry_log)

        log_type = entry_log['log_type']
        entry[log_type] = float(entry_log['timestamp'])
        entries[entry_id] = entry

    return entries


def analyze_entries(entries):
    entries_stats = []
    for entry_id, entry in entries.items():
        recorded_time = entry.get(journal.LOG_RECORDED, None)
        completed_time = entry.get(journal.LOG_COMPLETED, None)
        if recorded_time is None or completed_time is None:
            continue

        delta = completed_time - recorded_time
        entries_stats.append(EntryStats(
            entry_id=entry_id, time=delta, op=entry['op'],
            obj_type=entry['obj_type'], obj_id=entry['obj_id']))

    return entries_stats


def _percentile(timings, percent):
    location = int(len(timings) * (percent / 100.0))
    return int(timings[location])


def print_stats(output, slowest, entries_stats):
    entries_stats = sorted(
        entries_stats, key=lambda entry_stats: entry_stats.time)
    timings = [entry_stats.time for entry_stats in entries_stats]
    avg = sum(timings) / len(timings)

    six.print_('Average processing time: %ss' % avg, file=output)
    six.print_('90th percentile: %ss' % _percentile(timings, 90), file=output)
    six.print_('99th percentile: %ss' % _percentile(timings, 99), file=output)
    six.print_('99.9th percentile: %ss' % _percentile(timings, 99.9),
               file=output)
    six.print_('%s slowest entries:' % slowest, file=output)
    slowest = entries_stats[:-(slowest + 1):-1]
    for entry_stats in slowest:
        six.print_(ENTRY_LOG_TEMPLATE % entry_stats, file=output)


def get_content(file_name):
    return open(file_name) if file_name else sys.stdin


def main(output=sys.stdout):
    conf = setup_conf(output, sys.argv[1:])
    with get_content(conf.file) as content:
        entries = parse_log(content)

    entries_stats = analyze_entries(entries)

    if not entries_stats:
        six.print_('No entry statistics found.', file=output)
        return 1

    print_stats(output, conf.slowest, entries_stats)

    return 0


if __name__ == '__main__':
    exit(main())
