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
import six
import sys
import time

from oslo_log import log

from networking_odl._i18n import _LW


LOG = log.getLogger(__name__)


class CacheEntry(collections.namedtuple('CacheEntry', ['timeout', 'values'])):

    error = None

    @classmethod
    def create(cls, timeout, *values):
        return CacheEntry(timeout, list(values))

    def add_value(self, value):
        self.values.append(value)

    def is_expired(self, current_clock):
        return self.timeout <= current_clock

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


class Cache(object):
    '''Generic mapping class used to cache mapping

    Example of uses:
        - host name to IP addresses mapping
        - IP addresses to ODL networking topology elements mapping
    '''

    # TODO(Federico Ressi) after Mitaka: this class should store cached data
    # in a place shared between more hosts using a caching mechanism coherent
    # with other OpenStack libraries. This is specially interesting in the
    # context of reliability when there are more Neutron instances and direct
    # connection to ODL is broken.

    create_new_entry = CacheEntry.create

    def __init__(self, fetch_all_func):
        if not callable(fetch_all_func):
            message = 'Expected callable as parameter, got {!r}.'.format(
                fetch_all_func)
            raise TypeError(message)
        self._fetch_all = fetch_all_func
        self.clear()

    def clear(self):
        self._entries = collections.OrderedDict()

    def fetch(self, key, timeout):
        __, value = self.fetch_any([key], timeout=timeout)
        return value

    def fetch_any(self, keys, timeout):
        return next(self.fetch_all(keys=keys, timeout=timeout))

    def fetch_all(self, keys, timeout):
        # this mean now in numbers
        current_clock = time.clock()
        # this is the moment in the future in which new entries will expires
        new_entries_timeout = current_clock + timeout
        # entries to be fetched because missing or expired
        new_entries = collections.OrderedDict()
        # all entries missing or expired
        missing = collections.OrderedDict()
        # captured error for the case a problem has to be reported
        cause_exc_info = None

        for key in keys:
            entry = self._entries.get(key)
            if entry is None or entry.is_expired(current_clock) or entry.error:
                # this entry has to be fetched
                new_entries[key] = missing[key] =\
                    self.create_new_entry(new_entries_timeout)
            elif entry.values:
                # Yield existing entry
                for value in entry.values:
                    yield key, value
            else:
                # This entry is not expired and there were no error where it
                # has been fetch. Therefore we accept that there are no values
                # for given key until it expires. This is going to produce a
                # KeyError if it is still missing at the end of this function.
                missing[key] = entry

        if missing:
            if new_entries:
                # Fetch some entries and update the cache
                try:
                    new_entry_keys = tuple(new_entries)
                    for key, value in self._fetch_all(new_entry_keys):
                        entry = new_entries.get(key)
                        if entry:
                            # Add fresh new value
                            entry.add_value(value)
                        else:
                            # This key was not asked, but we take it in any
                            # way. "Noli equi dentes inspicere donati."
                            new_entries[key] = entry = self.create_new_entry(
                                new_entries_timeout, value)

                # pylint: disable=broad-except
                except Exception:
                    # Something has gone wrong: update and yield what got until
                    # now before raising any error
                    cause_exc_info = sys.exc_info()
                    LOG.warning(
                        _LW('Error fetching values for keys: %r'),
                        ', '.join(repr(k) for k in new_entry_keys),
                        exc_info=cause_exc_info)

                # update the cache with new fresh entries
                self._entries.update(new_entries)

            missing_keys = []
            for key, entry in six.iteritems(missing):
                if entry.values:
                    # yield entries that was missing before
                    for value in entry.values:
                        # Yield just fetched entry
                        yield key, value
                else:
                    if cause_exc_info:
                        # mark this entry as failed
                        entry.error = cause_exc_info
                    # after all this entry is still without any value
                    missing_keys.append(key)

            if missing_keys:
                # After all some entry is still missing, probably because the
                # key was invalid. It's time to raise an error.
                missing_keys = tuple(missing_keys)
                if not cause_exc_info:
                    # Search for the error cause in missing entries
                    for key in missing_keys:
                        error = self._entries[key].error
                        if error:
                            # A cached entry for which fetch method produced an
                            # error will produce the same error if fetch method
                            # fails to fetch it again without giving any error
                            # Is this what we want?
                            break

                    else:
                        # If the cause of the problem is not knwow then
                        # probably keys were wrong
                        message = 'Invalid keys: {!r}'.format(
                            ', '.join(missing_keys))
                        error = KeyError(message)

                    try:
                        raise error
                    except KeyError:
                        cause_exc_info = sys.exc_info()

                raise CacheFetchError(
                    missing_keys=missing_keys, cause_exc_info=cause_exc_info)


class CacheFetchError(KeyError):

    def __init__(self, missing_keys, cause_exc_info):
        super(CacheFetchError, self).__init__(str(cause_exc_info[1]))
        self.cause_exc_info = cause_exc_info
        self.missing_keys = missing_keys

    def reraise_cause(self):
        six.reraise(*self.cause_exc_info)
