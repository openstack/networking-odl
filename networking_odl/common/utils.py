# Copyright (c) 2014 Red Hat Inc.
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

import collections
import socket

from oslo_log import log

from networking_odl.common import cache

LOG = log.getLogger(__name__)


def try_del(d, keys):
    """Ignore key errors when deleting from a dictionary."""
    for key in keys:
        try:
            del d[key]
        except KeyError:
            pass


def _fetch_all_addresses_by_hostnames(hostnames):
    for name in hostnames:
        # it uses an ordered dict to avoid duplicates and keep order
        entries = collections.OrderedDict(
            (info[4][0], None) for info in socket.getaddrinfo(name, None))
        for entry in entries:
            yield name, entry


_addresses_by_name_cache = cache.Cache(_fetch_all_addresses_by_hostnames)


def get_addresses_by_name(name, time_to_live=60.0):
    """Gets and caches addresses for given name.

    This is a cached wrapper for function 'socket.getaddrinfo'.

    :returns: a sequence of unique addresses binded to given hostname.
    """

    try:
        results = _addresses_by_name_cache.fetch_all(
            [name], timeout=time_to_live)
        return tuple(address for name, address in results)
    except cache.CacheFetchError as error:
        error.reraise_cause()
