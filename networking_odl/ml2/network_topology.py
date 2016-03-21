# Copyright (c) 2015-2016 OpenStack Foundation
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

import abc
import importlib
import logging

import six
from six.moves.urllib import parse

from neutron.extensions import portbindings
from oslo_log import log
from oslo_serialization import jsonutils

from networking_odl.common import cache
from networking_odl.common import client
from networking_odl.common import utils
from networking_odl._i18n import _LI, _LW, _LE
from networking_odl.ml2 import port_binding


LOG = log.getLogger(__name__)


class NetworkTopologyManager(port_binding.PortBindingController):

    # the first valid vif type will be chosed following the order
    # on this list. This list can be modified to adapt to user preferences.
    valid_vif_types = [
        portbindings.VIF_TYPE_VHOST_USER, portbindings.VIF_TYPE_OVS]

    # List of class names of registered implementations of interface
    # NetworkTopologyParser
    network_topology_parsers = [
        'networking_odl.ml2.ovsdb_topology.OvsdbNetworkTopologyParser']

    def __init__(self, vif_details=None, client=None):
        # Details for binding port
        self._vif_details = vif_details or {portbindings.CAP_PORT_FILTER: True}

        # Rest client used for getting network topology from ODL
        self._client = client or NetworkTopologyClient.create_client()

        # Table of NetworkTopologyElement
        self._elements_by_ip = cache.Cache(
            self._fetch_and_parse_network_topology)

        # Parsers used for processing network topology
        self._parsers = list(self._create_parsers())

    def bind_port(self, port_context):
        """Set binding for a valid segment

        """
        host_name = port_context.host
        elements = list()
        try:
            # Append to empty list to add as much elements as possible
            # in the case it raises an exception
            elements.extend(self._fetch_elements_by_host(host_name))
        except Exception:
            LOG.exception(
                _LE('Error fetching elements for host %(host_name)r.'),
                {'host_name': host_name}, exc_info=1)

        if not elements:
            # In case it wasn't able to find any network topology element
            # for given host then it uses the legacy OVS one keeping the old
            # behaviour
            LOG.warning(
                _LW('Using legacy OVS network topology element for port '
                    'binding for host: %(host_name)r.'),
                {'host_name': host_name})

            # Imported here to avoid cyclic module dependencies
            from networking_odl.ml2 import ovsdb_topology
            elements = [ovsdb_topology.OvsdbNetworkTopologyElement()]

        # TODO(Federico Ressi): in the case there are more candidate virtual
        # switches instances for the same host it choses one for binding
        # port. As there isn't any know way to perform this selection it
        # selects a VIF type that is valid for all switches that have
        # been found and a VIF type valid for all them. This has to be improved
        for vif_type in self.valid_vif_types:
            vif_type_is_valid_for_all = True
            for element in elements:
                if vif_type not in element.valid_vif_types:
                    # it is invalid for at least one element: discard it
                    vif_type_is_valid_for_all = False
                    break

            if vif_type_is_valid_for_all:
                # This is the best VIF type valid for all elements
                LOG.debug(
                    "Found VIF type %(vif_type)r valid for all network "
                    "topology elements for host %(host_name)r.",
                    {'vif_type': vif_type, 'host_name': host_name})

                for element in elements:
                    # It assumes that any element could be good for given host
                    # In most of the cases I expect exactely one element for
                    # every compute host
                    try:
                        return element.bind_port(
                            port_context, vif_type, self._vif_details)

                    except Exception:
                        LOG.exception(
                            _LE('Network topology element has failed binding '
                                'port:\n%(element)s'),
                            {'element': element.to_json()})

        LOG.error(
            _LE('Unable to bind port element for given host and valid VIF '
                'types:\n'
                '\thostname: %(host_name)s\n'
                '\tvalid VIF types: %(valid_vif_types)s'),
            {'host_name': host_name,
             'valid_vif_types': ', '.join(self.valid_vif_types)})
        # TDOO(Federico Ressi): should I raise an exception here?

    def _create_parsers(self):
        for parser_name in self.network_topology_parsers:
            try:
                yield NetworkTopologyParser.create_parser(parser_name)

            except Exception:
                LOG.exception(
                    _LE('Error initializing topology parser: %(parser_name)r'),
                    {'parser_name': parser_name})

    def _fetch_elements_by_host(self, host_name, cache_timeout=60.0):
        '''Yields all network topology elements referring to given host name

        '''

        host_addresses = [host_name]
        try:
            # It uses both compute host name and known IP addresses to
            # recognize topology elements valid for given computed host
            ip_addresses = utils.get_addresses_by_name(host_name)
        except Exception:
            ip_addresses = []
            LOG.exception(
                _LE('Unable to resolve IP addresses for host %(host_name)r'),
                {'host_name': host_name})
        else:
            host_addresses.extend(ip_addresses)

        yield_elements = set()
        try:
            for __, element in self._elements_by_ip.fetch_all(
                    host_addresses, cache_timeout):
                # yields every element only once
                if element not in yield_elements:
                    yield_elements.add(element)
                    yield element

        except cache.CacheFetchError as error:
            # This error is expected on most of the cases because typically not
            # all host_addresses maps to a network topology element.
            if yield_elements:
                # As we need only one element for every host we ignore the
                # case in which others host addresseses didn't map to any host
                LOG.debug(
                    'Host addresses not found in networking topology: %s',
                    ', '.join(error.missing_keys))
            else:
                LOG.exception(
                    _LE('No such network topology elements for given host '
                        '%(host_name)r and given IPs: %(ip_addresses)s.'),
                    {'host_name': host_name,
                     'ip_addresses': ", ".join(ip_addresses)})
                error.reraise_cause()

    def _fetch_and_parse_network_topology(self, addresses):
        # The cache calls this method to fecth new elements when at least one
        # of the addresses is not in the cache or it has expired.

        # pylint: disable=unused-argument
        LOG.info(_LI('Fetch network topology from ODL.'))
        response = self._client.get()
        response.raise_for_status()

        network_topology = response.json()
        if LOG.isEnabledFor(logging.DEBUG):
            topology_str = jsonutils.dumps(
                network_topology, sort_keys=True, indent=4,
                separators=(',', ': '))
            LOG.debug("Got network topology:\n%s", topology_str)

        at_least_one_element_for_asked_addresses = False
        for parser in self._parsers:
            try:
                for element in parser.parse_network_topology(network_topology):
                    if not isinstance(element, NetworkTopologyElement):
                        raise TypeError(
                            "Yield element doesn't implement interface "
                            "'NetworkTopologyElement': {!r}".format(element))
                    # the same element can be known by more host addresses
                    for host_address in element.host_addresses:
                        if host_address in addresses:
                            at_least_one_element_for_asked_addresses = True
                        yield host_address, element
            except Exception:
                LOG.exception(
                    _LE("Parser %(parser)r failed to parse network topology."),
                    {'parser': parser})

        if not at_least_one_element_for_asked_addresses:
            # this will mark entries for given addresses as failed to allow
            # calling this method again as soon it is requested and avoid
            # waiting for cache expiration
            raise ValueError(
                'No such topology element for given host addresses: {}'.format(
                    ', '.join(addresses)))


@six.add_metaclass(abc.ABCMeta)
class NetworkTopologyParser(object):

    @classmethod
    def create_parser(cls, parser_class_name):
        '''Creates a 'NetworkTopologyParser' of given class name.

        '''
        module_name, class_name = parser_class_name.rsplit('.', 1)
        module = importlib.import_module(module_name)
        clss = getattr(module, class_name)
        if not issubclass(clss, cls):
            raise TypeError(
                "Class {class_name!r} of module {module_name!r} doesn't "
                "implement 'NetworkTopologyParser' interface.".format(
                    class_name=class_name, module_name=module_name))
        return clss()

    @abc.abstractmethod
    def parse_network_topology(self, network_topology):
        '''Parses OpenDaylight network topology

        Yields all network topology elements implementing
        'NetworkTopologyElement' interface found in given network topology.
        '''


@six.add_metaclass(abc.ABCMeta)
class NetworkTopologyElement(object):

    @abc.abstractproperty
    def host_addresses(self):
        '''List of known host addresses of a single compute host

        Either host names and ip addresses are valid.
        Neutron host controller must know at least one of these compute host
        names or ip addresses to find this element.
        '''

    @abc.abstractproperty
    def valid_vif_types(self):
        '''Returns a tuple listing VIF types supported by the compute node

        '''

    @abc.abstractmethod
    def bind_port(self, port_context, vif_type, vif_details):
        '''Bind port context using given vif type and vif details

        This method is expected to search for a valid segment and then
        call port_context.set_binding()
        '''

    def to_dict(self):
        cls = type(self)
        return {
            'class': cls.__module__ + '.' + cls.__name__,
            'host_addresses': list(self.host_addresses),
            'valid_vif_types': list(self.valid_vif_types)}

    def to_json(self):
        return jsonutils.dumps(
            self.to_dict(), sort_keys=True, indent=4, separators=(',', ': '))


class NetworkTopologyClient(client.OpenDaylightRestClient):

    _GET_ODL_NETWORK_TOPOLOGY_URL =\
        'restconf/operational/network-topology:network-topology'

    def __init__(self, url, username, password, timeout):
        if url:
            url = parse.urlparse(url)
            port = ''
            if url.port:
                port = ':' + str(url.port)
            topology_url = '{}://{}{}/{}'.format(
                url.scheme, url.hostname, port,
                self._GET_ODL_NETWORK_TOPOLOGY_URL)
        else:
            topology_url = None
        super(NetworkTopologyClient, self).__init__(
            topology_url, username, password, timeout)
