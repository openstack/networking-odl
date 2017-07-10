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

import tokenize

from hacking.checks import docstrings

# TODO(yamahata): enable neutron checking
# from neutron.hacking import checks
from neutron_lib.hacking import checks

_ND01_MSG = "ND01: use OpenDaylight (capital D) instead of Opendaylight"
_ND01_OPENDAYLIGHT = 'Opendaylight'


def check_opendaylight_lowercase(logical_line, filename):
    """ND01 - Enforce using OpenDaylight."""
    if _ND01_OPENDAYLIGHT in logical_line:
        pos = logical_line.find(_ND01_OPENDAYLIGHT)
        yield (pos, _ND01_MSG)


def check_opendaylight_lowercase_comment(
        physical_line, previous_logical, tokens):
    """ND01 - Enforce using OpenDaylight in comment."""
    for token_type, text, start_index, _, _ in tokens:
        if token_type == tokenize.COMMENT:
            pos = physical_line.find(_ND01_OPENDAYLIGHT)
            if pos >= 0:
                return (pos, _ND01_MSG + " in comment")


def check_opendaylight_lowercase_docstring(
        physical_line, previous_logical, tokens):
    """ND01 - Enforce using OpenDaylight in docstring."""
    docstring = docstrings.is_docstring(tokens, previous_logical)
    if docstring and _ND01_OPENDAYLIGHT in docstring:
        pos = physical_line.find(_ND01_OPENDAYLIGHT)
        return (pos, _ND01_MSG + " in docstring")


def factory(register):
    checks.factory(register)
    register(check_opendaylight_lowercase)
    register(check_opendaylight_lowercase_comment)
    register(check_opendaylight_lowercase_docstring)
