# Copyright 2017 Intel Corporation.
# Copyright 2017 Isaku Yamahata <isaku.yamahata at intel com>
#                               <isaku.yamahata at gmail com>
# All Rights Reserved.
#
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

import re
import tokenize

from hacking.checks import docstrings

# TODO(yamahata): enable neutron checking
# from neutron.hacking import checks
from neutron_lib.hacking import checks

_ND01_MSG = (
    "ND01: use OpenDaylight (capital D) instead of Opendaylight")  # noqa
_ND01_OPENDAYLIGHT = 'Opendaylight'  # noqa

_ND02_MSG = (
    "ND02: use the config fixture provided by oslo_config and use config()"
    " instead of %s")  # noqa

_ND02_REGEXP_DIRECT = re.compile(r'cfg\.CONF\..* =')

_ND03_MSG = (
    "ND03: The import of %s has a redundant alias."
)
_ND03_REGEXP_REDUNDANT_IMPORT_ALIAS = re.compile(r'.*import (.+) as \1$')


def check_opendaylight_lowercase(logical_line, filename, noqa):
    """ND01 - Enforce using OpenDaylight."""
    if noqa:
        return

    if _ND01_OPENDAYLIGHT in logical_line:
        pos = logical_line.find(_ND01_OPENDAYLIGHT)
        yield (pos, _ND01_MSG)


def _check_opendaylight_lowercase(logical_line, tokens, noqa, token_type):
    """ND01 - Enforce using OpenDaylight in given token."""
    if noqa:
        return

    for _token_type, text, start_index, _, _ in tokens:
        if _token_type == token_type:
            pos = text.find(_ND01_OPENDAYLIGHT)
            if pos >= 0:
                msg = "{} in {}".format(
                    _ND01_MSG, tokenize.tok_name[token_type].lower())
                yield (start_index[1] + pos, msg)


def check_opendaylight_lowercase_comment(logical_line, tokens, noqa):
    """ND01 - Enforce using OpenDaylight in comment."""

    for res in _check_opendaylight_lowercase(
            logical_line, tokens, noqa, tokenize.COMMENT):
        yield res


def check_opendaylight_lowercase_string(logical_line, tokens, noqa):
    """ND01 - Enforce using OpenDaylight in string."""

    for res in _check_opendaylight_lowercase(
            logical_line, tokens, noqa, tokenize.STRING):
        yield res


def check_opendaylight_lowercase_docstring(
        physical_line, previous_logical, tokens):
    """ND01 - Enforce using OpenDaylight in docstring."""
    docstring = docstrings.is_docstring(tokens, previous_logical)
    if docstring and _ND01_OPENDAYLIGHT in docstring:
        pos = physical_line.find(_ND01_OPENDAYLIGHT)
        return (pos, _ND01_MSG + " in docstring")
    return None


def check_config_over_set_override(logical_line, filename, noqa):
    """ND02 - Enforcement of config fixture

    Enforce agreement of not use set_override() but use
    instead the fixture's config() helper for tests.
    """

    if noqa:
        return

    if 'networking_odl/tests/' not in filename:
        return

    if 'cfg.CONF.set_override' in logical_line:
        yield (0, _ND02_MSG % "using cfg.CONF.set_override()")


def check_config_over_direct_override(logical_line, filename, noqa):
    """ND02 - Enforcement of config fixture

    Enforce usage of the fixture's config() helper instead
    of overriding a setting directly
    """

    if noqa:
        return

    if 'networking_odl/tests/' not in filename:
        return

    if _ND02_REGEXP_DIRECT.match(logical_line):
        yield (0, _ND02_MSG % "overriding it directly.")


def check_redundant_import_alias(logical_line):
    """ND03 - Checking no redundant import alias.

    ND03: from neutron.plugins.ml2 import driver_context as driver_context
    OK: from neutron.plugins.ml2 import driver_context
    """

    match = re.match(_ND03_REGEXP_REDUNDANT_IMPORT_ALIAS, logical_line)
    if match:
        yield (0, _ND03_MSG % match.group(1))


def factory(register):
    checks.factory(register)
    register(check_opendaylight_lowercase)
    register(check_opendaylight_lowercase_comment)
    register(check_opendaylight_lowercase_string)
    register(check_opendaylight_lowercase_docstring)
    register(check_config_over_set_override)
    register(check_config_over_direct_override)
    register(check_redundant_import_alias)
