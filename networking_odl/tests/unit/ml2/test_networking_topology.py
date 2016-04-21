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


from os import path

import mock
from oslo_log import log
from oslo_serialization import jsonutils
import requests

from neutron.common import constants as n_constants
from neutron.extensions import portbindings
from neutron.plugins.common import constants
from neutron.plugins.ml2 import driver_api
from neutron.plugins.ml2 import driver_context

from networking_odl.common import cache
from networking_odl.ml2 import mech_driver
from networking_odl.ml2 import mech_driver_v2
from networking_odl.ml2 import network_topology
from networking_odl.tests import base


LOG = log.getLogger(__name__)


class TestNetworkTopologyManager(base.DietTestCase):

    # pylint: disable=protected-access

    # given valid  and invalid segments
    valid_segment = {
        driver_api.ID: 'API_ID',
        driver_api.NETWORK_TYPE: constants.TYPE_LOCAL,
        driver_api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        driver_api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    invalid_segment = {
        driver_api.ID: 'API_ID',
        driver_api.NETWORK_TYPE: constants.TYPE_NONE,
        driver_api.SEGMENTATION_ID: 'API_SEGMENTATION_ID',
        driver_api.PHYSICAL_NETWORK: 'API_PHYSICAL_NETWORK'}

    segments_to_bind = [valid_segment, invalid_segment]

    def setUp(self):
        super(TestNetworkTopologyManager, self).setUp()
        self.patch(network_topology.LOG, 'isEnabledFor', lambda level: True)
        # patch given configuration
        self.cfg = mocked_cfg = self.patch(network_topology.client, 'cfg')
        mocked_cfg.CONF.ml2_odl.url =\
            'http://localhost:8181/controller/nb/v2/neutron'
        mocked_cfg.CONF.ml2_odl.username = 'admin'
        mocked_cfg.CONF.ml2_odl.password = 'admin'
        mocked_cfg.CONF.ml2_odl.timeout = 5

    @mock.patch.object(cache, 'LOG')
    @mock.patch.object(network_topology, 'LOG')
    def test_fetch_elements_by_host_with_no_entry(
            self, network_topology_logger, cache_logger):
        given_client = self.mock_client('ovs_topology.json')
        self.mock_get_addresses_by_name(['127.0.0.1', '192.168.0.1'])
        given_network_topology = network_topology.NetworkTopologyManager(
            client=given_client)

        try:
            next(given_network_topology._fetch_elements_by_host(
                 'some_host_name'))
        except ValueError as error:
            cache_logger.warning.assert_called_once_with(
                'Error fetching values for keys: %r',
                "'some_host_name', '127.0.0.1', '192.168.0.1'",
                exc_info=(ValueError, error, mock.ANY))
            network_topology_logger.exception.assert_called_once_with(
                'No such network topology elements for given host '
                '%(host_name)r and given IPs: %(ip_addresses)s.',
                {'ip_addresses': '127.0.0.1, 192.168.0.1',
                 'host_name': 'some_host_name'})
        else:
            self.fail('Expected ValueError being raised.')

    def test_fetch_element_with_ovs_entry(self):
        given_client = self.mock_client('ovs_topology.json')
        self.mock_get_addresses_by_name(['127.0.0.1', '10.237.214.247'])
        given_network_topology = network_topology.NetworkTopologyManager(
            client=given_client)

        elements = given_network_topology._fetch_elements_by_host(
            'some_host_name.')

        self.assertEqual([
            {'class':
             'networking_odl.ml2.ovsdb_topology.OvsdbNetworkTopologyElement',
             'has_datapath_type_netdev': False,
             'host_addresses': ['10.237.214.247'],
             'support_vhost_user': False,
             'uuid': 'c4ad780f-8f91-4fa4-804e-dd16beb191e2',
             'valid_vif_types': [portbindings.VIF_TYPE_OVS]}],
            [e.to_dict() for e in elements])

    def test_fetch_elements_with_vhost_user_entry(self):
        given_client = self.mock_client('vhostuser_topology.json')
        self.mock_get_addresses_by_name(['127.0.0.1', '192.168.66.1'])
        given_network_topology = network_topology.NetworkTopologyManager(
            client=given_client)

        elements = given_network_topology._fetch_elements_by_host(
            'some_host_name.')

        self.assertEqual([
            {'class':
             'networking_odl.ml2.ovsdb_topology.OvsdbNetworkTopologyElement',
             'has_datapath_type_netdev': True,
             'host_addresses': ['192.168.66.1'],
             'support_vhost_user': True,
             'uuid': 'c805d82d-a5d8-419d-bc89-6e3713ff9f6c',
             'valid_vif_types': [portbindings.VIF_TYPE_VHOST_USER,
                                 portbindings.VIF_TYPE_OVS],
             'port_prefix': 'vhu',
             'vhostuser_socket_dir': '/var/run/openvswitch'}],
            [e.to_dict() for e in elements])

    def mock_get_addresses_by_name(self, ips):
        utils = self.patch(
            network_topology, 'utils',
            mock.Mock(
                get_addresses_by_name=mock.Mock(return_value=tuple(ips))))
        return utils.get_addresses_by_name

    def mock_client(self, topology_name=None):

        mocked_client = mock.NonCallableMock(
            specs=network_topology.NetworkTopologyClient)

        if topology_name:
            cached_file_path = path.join(path.dirname(__file__), topology_name)

            with open(cached_file_path, 'rt') as fd:
                topology = jsonutils.loads(str(fd.read()), encoding='utf-8')

            mocked_client.get().json.return_value = topology

        return mocked_client

    def test_bind_port_from_mech_driver_with_ovs(self):

        given_client = self.mock_client('ovs_topology.json')
        self.mock_get_addresses_by_name(['127.0.0.1', '10.237.214.247'])
        given_network_topology = network_topology.NetworkTopologyManager(
            vif_details={'some': 'detail'},
            client=given_client)
        self.patch(
            network_topology, 'NetworkTopologyManager',
            return_value=given_network_topology)

        given_driver = mech_driver.OpenDaylightMechanismDriver()
        given_driver.odl_drv = mech_driver.OpenDaylightDriver()
        given_port_context = self.given_port_context()

        # when port is bound
        given_driver.bind_port(given_port_context)

        # then context binding is setup with returned vif_type and valid
        # segment api ID
        given_port_context.set_binding.assert_called_once_with(
            self.valid_segment[driver_api.ID], portbindings.VIF_TYPE_OVS,
            {'some': 'detail'}, status=n_constants.PORT_STATUS_ACTIVE)

    def test_bind_port_from_mech_driver_with_vhostuser(self):

        given_client = self.mock_client('vhostuser_topology.json')
        self.mock_get_addresses_by_name(['127.0.0.1', '192.168.66.1'])
        given_network_topology = network_topology.NetworkTopologyManager(
            vif_details={'some': 'detail'},
            client=given_client)
        self.patch(
            network_topology, 'NetworkTopologyManager',
            return_value=given_network_topology)

        given_driver = mech_driver.OpenDaylightMechanismDriver()
        given_driver.odl_drv = mech_driver.OpenDaylightDriver()
        given_port_context = self.given_port_context()

        # when port is bound
        given_driver.bind_port(given_port_context)

        expected_vif_details = {
            'vhostuser_socket': '/var/run/openvswitch/vhuCURRENT_CON',
            'vhostuser_ovs_plug': True,
            'some': 'detail',
            'vhostuser_mode': 'client'}

        # then context binding is setup with returned vif_type and valid
        # segment api ID
        given_port_context.set_binding.assert_called_once_with(
            self.valid_segment[driver_api.ID],
            portbindings.VIF_TYPE_VHOST_USER,
            expected_vif_details, status=n_constants.PORT_STATUS_ACTIVE)

    def test_bind_port_from_mech_driver_v2_with_ovs(self):
        given_client = self.mock_client('ovs_topology.json')
        self.mock_get_addresses_by_name(['127.0.0.1', '10.237.214.247'])
        given_network_topology = network_topology.NetworkTopologyManager(
            vif_details={'some': 'detail'},
            client=given_client)
        self.patch(
            network_topology, 'NetworkTopologyManager',
            return_value=given_network_topology)

        given_driver = mech_driver_v2.OpenDaylightMechanismDriver()
        given_port_context = self.given_port_context()

        given_driver.initialize()
        # when port is bound
        given_driver.bind_port(given_port_context)

        # then context binding is setup with returned vif_type and valid
        # segment api ID
        given_port_context.set_binding.assert_called_once_with(
            self.valid_segment[driver_api.ID], portbindings.VIF_TYPE_OVS,
            {'some': 'detail'}, status=n_constants.PORT_STATUS_ACTIVE)

    def test_bind_port_from_mech_driver_v2_with_vhostuser(self):
        given_client = self.mock_client('vhostuser_topology.json')
        self.mock_get_addresses_by_name(['127.0.0.1', '192.168.66.1'])
        given_network_topology = network_topology.NetworkTopologyManager(
            vif_details={'some': 'detail'},
            client=given_client)
        self.patch(
            network_topology, 'NetworkTopologyManager',
            return_value=given_network_topology)

        given_driver = mech_driver_v2.OpenDaylightMechanismDriver()
        given_driver._network_topology = given_network_topology
        given_port_context = self.given_port_context()

        given_driver.initialize()
        # when port is bound
        given_driver.bind_port(given_port_context)

        expected_vif_details = {
            'vhostuser_socket': '/var/run/openvswitch/vhuCURRENT_CON',
            'vhostuser_ovs_plug': True,
            'some': 'detail',
            'vhostuser_mode': 'client'}

        # then context binding is setup with returned vif_type and valid
        # segment api ID
        given_port_context.set_binding.assert_called_once_with(
            self.valid_segment[driver_api.ID],
            portbindings.VIF_TYPE_VHOST_USER,
            expected_vif_details, status=n_constants.PORT_STATUS_ACTIVE)

    def test_bind_port_with_vif_type_ovs(self):
        given_topology = self._mock_network_topology(
            'ovs_topology.json', vif_details={'much': 'details'})
        given_port_context = self.given_port_context()

        # when port is bound
        given_topology.bind_port(given_port_context)

        # then context binding is setup wit returned vif_type and valid
        # segment api ID
        given_port_context.set_binding.assert_called_once_with(
            self.valid_segment[driver_api.ID], portbindings.VIF_TYPE_OVS,
            {'much': 'details'}, status=n_constants.PORT_STATUS_ACTIVE)

    def test_bind_port_with_vif_type_vhost_user(self):
        given_topology = self._mock_network_topology(
            'vhostuser_topology.json', vif_details={'much': 'details'})
        given_port_context = self.given_port_context()

        # when port is bound
        given_topology.bind_port(given_port_context)

        # then context binding is setup wit returned vif_type and valid
        # segment api ID
        given_port_context.set_binding.assert_called_once_with(
            self.valid_segment[driver_api.ID],
            portbindings.VIF_TYPE_VHOST_USER,
            {'vhostuser_socket': '/var/run/openvswitch/vhuCURRENT_CON',
             'vhostuser_ovs_plug': True, 'vhostuser_mode': 'client',
             'much': 'details'},
            status=n_constants.PORT_STATUS_ACTIVE)

    @mock.patch.object(network_topology, 'LOG')
    def test_bind_port_without_valid_segment(self, logger):
        given_topology = self._mock_network_topology('ovs_topology.json')
        given_port_context = self.given_port_context(
            given_segments=[self.invalid_segment])

        # when port is bound
        given_topology.bind_port(given_port_context)

        self.assertFalse(given_port_context.set_binding.called)
        logger.exception.assert_called_once_with(
            'Network topology element has failed binding port:\n%(element)s',
            {'element': mock.ANY})
        logger.error.assert_called_once_with(
            'Unable to bind port element for given host and valid VIF types:\n'
            '\thostname: %(host_name)s\n'
            '\tvalid VIF types: %(valid_vif_types)s',
            {'host_name': 'some_host', 'valid_vif_types': 'vhostuser, ovs'})

    def _mock_network_topology(self, given_topology, vif_details=None):
        self.mock_get_addresses_by_name(
            ['127.0.0.1', '10.237.214.247', '192.168.66.1'])
        return network_topology.NetworkTopologyManager(
            client=self.mock_client(given_topology),
            vif_details=vif_details)

    def given_port_context(self, given_segments=None):
        # given NetworkContext
        network = mock.MagicMock(spec=driver_api.NetworkContext)

        if given_segments is None:
            given_segments = self.segments_to_bind

        # given port context
        return mock.MagicMock(
            spec=driver_context.PortContext,
            current={'id': 'CURRENT_CONTEXT_ID'},
            host='some_host',
            segments_to_bind=given_segments,
            network=network,
            _new_bound_segment=self.valid_segment)

    NETOWORK_TOPOLOGY_URL =\
        'http://localhost:8181/'\
        'restconf/operational/network-topology:network-topology/'

    def mock_request_network_topology(self, file_name):
        cached_file_path = path.join(
            path.dirname(__file__), file_name + '.json')

        if path.isfile(cached_file_path):
            LOG.debug('Loading topology from file: %r', cached_file_path)
            with open(cached_file_path, 'rt') as fd:
                topology = jsonutils.loads(str(fd.read()), encoding='utf-8')
        else:
            LOG.debug(
                'Getting topology from ODL: %r', self.NETOWORK_TOPOLOGY_URL)
            request = requests.get(
                self.NETOWORK_TOPOLOGY_URL, auth=('admin', 'admin'),
                headers={'Content-Type': 'application/json'})
            request.raise_for_status()

            with open(cached_file_path, 'wt') as fd:
                LOG.debug('Saving topology to file: %r', cached_file_path)
                topology = request.json()
                jsonutils.dump(
                    topology, fd, sort_keys=True, indent=4,
                    separators=(',', ': '))

        mocked_request = self.patch(
            mech_driver.odl_client.requests, 'request',
            return_value=mock.MagicMock(
                spec=requests.Response,
                json=mock.MagicMock(return_value=topology)))

        return mocked_request


class TestNetworkTopologyClient(base.DietTestCase):

    given_host = 'given.host'
    given_port = 1234
    given_url_with_port = 'http://{}:{}/'.format(
        given_host, given_port)
    given_url_without_port = 'http://{}/'.format(given_host)
    given_username = 'GIVEN_USERNAME'
    given_password = 'GIVEN_PASSWORD'
    given_timeout = 20

    def given_client(
            self, url=None, username=None, password=None, timeout=None):
        return network_topology.NetworkTopologyClient(
            url=url or self.given_url_with_port,
            username=username or self.given_username,
            password=password or self.given_password,
            timeout=timeout or self.given_timeout)

    def test_constructor(self):
        # When client is created
        rest_client = network_topology.NetworkTopologyClient(
            url=self.given_url_with_port,
            username=self.given_username,
            password=self.given_password,
            timeout=self.given_timeout)

        self.assertEqual(
            self.given_url_with_port +
            'restconf/operational/network-topology:network-topology',
            rest_client.url)
        self.assertEqual(
            (self.given_username, self.given_password), rest_client.auth)
        self.assertEqual(self.given_timeout, rest_client.timeout)

    def test_request_with_port(self):
        # Given rest client and used 'requests' module
        given_client = self.given_client()
        mocked_requests_module = self.mocked_requests()

        # When a request is performed
        result = given_client.request(
            'GIVEN_METHOD', 'given/path', 'GIVEN_DATA')

        # Then request method is called
        mocked_requests_module.request.assert_called_once_with(
            'GIVEN_METHOD',
            url='http://given.host:1234/restconf/operational/' +
            'network-topology:network-topology/given/path',
            auth=(self.given_username, self.given_password),
            data='GIVEN_DATA', headers={'Content-Type': 'application/json'},
            timeout=self.given_timeout)

        # Then request method result is returned
        self.assertIs(mocked_requests_module.request.return_value, result)

    def test_request_without_port(self):
        # Given rest client and used 'requests' module
        given_client = self.given_client(url=self.given_url_without_port)
        mocked_requests_module = self.mocked_requests()

        # When a request is performed
        result = given_client.request(
            'GIVEN_METHOD', 'given/path', 'GIVEN_DATA')

        # Then request method is called
        mocked_requests_module.request.assert_called_once_with(
            'GIVEN_METHOD',
            url='http://given.host/restconf/operational/' +
            'network-topology:network-topology/given/path',
            auth=(self.given_username, self.given_password),
            data='GIVEN_DATA', headers={'Content-Type': 'application/json'},
            timeout=self.given_timeout)

        # Then request method result is returned
        self.assertIs(mocked_requests_module.request.return_value, result)

    def test_get(self):
        # Given rest client and used 'requests' module
        given_client = self.given_client()
        mocked_requests_module = self.mocked_requests()

        # When a request is performed
        result = given_client.get('given/path', 'GIVEN_DATA')

        # Then request method is called
        mocked_requests_module.request.assert_called_once_with(
            'get',
            url='http://given.host:1234/restconf/operational/' +
            'network-topology:network-topology/given/path',
            auth=(self.given_username, self.given_password),
            data='GIVEN_DATA', headers={'Content-Type': 'application/json'},
            timeout=self.given_timeout)

        # Then request method result is returned
        self.assertIs(mocked_requests_module.request.return_value, result)

    def mocked_requests(self):
        return self.patch(network_topology.client, 'requests')
