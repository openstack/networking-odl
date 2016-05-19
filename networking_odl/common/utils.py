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
from networking_odl.common import constants as odl_const

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

    :returns: a sequence of unique addresses bound to given hostname.
    """

    try:
        results = _addresses_by_name_cache.fetch_all(
            [name], timeout=time_to_live)
        return tuple(address for name, address in results)
    except cache.CacheFetchError as error:
        error.reraise_cause()


def make_url_object(object_type):
    if object_type[-1:] == 'y':
        obj_pl = neutronify(object_type[:-1] + 'ies')
    else:
        obj_pl = neutronify(object_type + 's')

    prefix = odl_const.PREFIXES.get(object_type, None)
    if prefix is not None:
        obj_pl = prefix + '/' + obj_pl
    return obj_pl


# TODO(manjeets) consolidate this method with make_url_object
def neutronify(name):
    """Adjust the resource name for use with Neutron's API"""
    return name.replace('_', '-')
