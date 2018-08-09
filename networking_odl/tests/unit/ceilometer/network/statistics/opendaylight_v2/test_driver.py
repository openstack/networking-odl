#
# Copyright 2017 Ericsson India Global Services Pvt Ltd. All rights reserved.
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
import abc

import mock
from oslotest import base
import six
from six.moves.urllib import parse as url_parse

from ceilometer import service
from networking_odl.ceilometer.network.statistics.opendaylight_v2 import driver
from oslo_utils import uuidutils

ADMIN_ID = uuidutils.generate_uuid()
PORT_1_TENANT_ID = uuidutils.generate_uuid()
PORT_2_TENANT_ID = uuidutils.generate_uuid()
PORT_1_ID = uuidutils.generate_uuid()
PORT_2_ID = uuidutils.generate_uuid()


@six.add_metaclass(abc.ABCMeta)
class _Base(base.BaseTestCase):

    @abc.abstractproperty
    def switch_data(self):
        pass

    fake_odl_url = url_parse.ParseResult('opendaylight.v2',
                                         'localhost:8080',
                                         'controller/statistics',
                                         None,
                                         None,
                                         None)

    fake_params = url_parse.parse_qs('user=admin&password=admin&scheme=http&'
                                     'auth=basic')

    def setUp(self):
        super(_Base, self).setUp()
        self.addCleanup(mock.patch.stopall)
        conf = service.prepare_service([], [])
        self.driver = driver.OpenDaylightDriver(conf)
        ks_client = mock.Mock(auth_token='fake_token')
        ks_client.projects.find.return_value = mock.Mock(name='admin',
                                                         id=ADMIN_ID)
        self.ks_client = mock.patch('ceilometer.keystone_client.get_client',
                                    return_value=ks_client).start()
        self.get_statistics = mock.patch(
            'networking_odl.ceilometer.network.statistics.opendaylight_v2.'
            'client.SwitchStatisticsAPIClient.get_statistics',
            return_value=self.switch_data).start()

    def _test_for_meter(self, meter_name, expected_data):
        sample_data = self.driver.get_sample_data(meter_name,
                                                  self.fake_odl_url,
                                                  self.fake_params,
                                                  {})

        self.assertEqual(expected_data, list(sample_data))


class TestOpenDayLightDriverInvalid(_Base):

    switch_data = {"flow_capable_switches": []}

    def test_not_implemented_meter(self):
        sample_data = self.driver.get_sample_data('egg',
                                                  self.fake_odl_url,
                                                  self.fake_params,
                                                  {})
        self.assertIsNone(sample_data)

        sample_data = self.driver.get_sample_data('switch.table.egg',
                                                  self.fake_odl_url,
                                                  self.fake_params,
                                                  {})
        self.assertIsNone(sample_data)

    def test_cache(self):
        cache = {}
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params,
                                    cache)
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params,
                                    cache)
        self.assertEqual(1, self.get_statistics.call_count)

        cache = {}
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params,
                                    cache)
        self.assertEqual(2, self.get_statistics.call_count)

    def test_http_error(self):

        mock.patch(
            'networking_odl.ceilometer.network.statistics.opendaylight_v2.'
            'client.SwitchStatisticsAPIClient.get_statistics',
            side_effect=Exception()).start()

        sample_data = self.driver.get_sample_data('switch',
                                                  self.fake_odl_url,
                                                  self.fake_params,
                                                  {})

        self.assertEqual(0, len(sample_data))

        mock.patch(
            'networking_odl.ceilometer.network.statistics.opendaylight_v2.'
            'client.SwitchStatisticsAPIClient.get_statistics',
            side_effect=[Exception(), self.switch_data]).start()
        cache = {}
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params,
                                    cache)

        self.assertIn('network.statistics.opendaylight_v2', cache)


class TestOpenDayLightDriverSimple(_Base):

    switch_data = {
        "flow_capable_switches": [{
            "packet_in_messages_received": 501,
            "packet_out_messages_sent": 300,
            "ports": 1,
            "flow_datapath_id": 55120148545607,
            "switch_port_counters": [{
                "bytes_received": 0,
                "bytes_sent": 0,
                "duration": 600,
                "packets_internal_received": 444,
                "packets_internal_sent": 0,
                "packets_received": 0,
                "packets_received_drop": 0,
                "packets_received_error": 0,
                "packets_sent": 0,
                "port_id": 4,
                "tenant_id": PORT_1_TENANT_ID,
                "uuid": PORT_1_ID
            }],
            "table_counters": [{
                "flow_count": 90,
                "table_id": 0
            }]
        }]
    }

    def test_meter_switch(self):
        expected_data = [
            (1, "55120148545607",
             {'controller': 'OpenDaylight_V2'},
             ADMIN_ID),
        ]
        self._test_for_meter('switch', expected_data)

    def test_meter_switch_ports(self):
        expected_data = [
            (1, "55120148545607",
             {'controller': 'OpenDaylight_V2'},
             ADMIN_ID)
        ]
        self._test_for_meter('switch.ports', expected_data)

    def test_meter_switch_port(self):
        expected_data = [
            (1, '55120148545607:4', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 4,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port', expected_data)

    def test_meter_switch_port_uptime(self):
        expected_data = [
            (600, '55120148545607:4', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 4,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.uptime', expected_data)

    def test_meter_switch_port_receive_packets(self):
        expected_data = [
            (0, '55120148545607:4', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 4,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.receive.packets', expected_data)

    def test_meter_switch_port_transmit_packets(self):
        expected_data = [
            (0, '55120148545607:4', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 4,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.transmit.packets', expected_data)

    def test_meter_switch_port_receive_bytes(self):
        expected_data = [
            (0, '55120148545607:4', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 4,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.receive.bytes', expected_data)

    def test_meter_switch_port_transmit_bytes(self):
        expected_data = [
            (0, '55120148545607:4', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 4,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.transmit.bytes', expected_data)

    def test_meter_switch_port_receive_drops(self):
        expected_data = [
            (0, '55120148545607:4', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 4,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.receive.drops', expected_data)

    def test_meter_switch_port_receive_errors(self):
        expected_data = [
            (0, '55120148545607:4', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 4,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.receive.errors', expected_data)

    def test_meter_port(self):
        expected_data = [
            (1, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port', expected_data)

    def test_meter_port_uptime(self):
        expected_data = [
            (600, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.uptime', expected_data)

    def test_meter_port_receive_packets(self):
        expected_data = [
            (0, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.receive.packets', expected_data)

    def test_meter_port_transmit_packets(self):
        expected_data = [
            (0, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.transmit.packets', expected_data)

    def test_meter_port_receive_bytes(self):
        expected_data = [
            (0, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.receive.bytes', expected_data)

    def test_meter_port_transmit_bytes(self):
        expected_data = [
            (0, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.transmit.bytes', expected_data)

    def test_meter_port_receive_drops(self):
        expected_data = [
            (0, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.receive.drops', expected_data)

    def test_meter_port_receive_errors(self):
        expected_data = [
            (0, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.receive.errors', expected_data)

    def test_meter_switch_table_active_entries(self):
        expected_data = [
            (90, "55120148545607:table:0", {
                'switch': '55120148545607',
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.table.active.entries', expected_data)


class TestOpenDayLightDriverComplex(_Base):

    switch_data = {
        "flow_capable_switches": [{
            "packet_in_messages_received": 501,
            "packet_out_messages_sent": 300,
            "ports": 3,
            "flow_datapath_id": 55120148545607,
            "switch_port_counters": [{
                "bytes_received": 0,
                "bytes_sent": 512,
                "duration": 200,
                "packets_internal_received": 444,
                "packets_internal_sent": 0,
                "packets_received": 10,
                "packets_received_drop": 0,
                "packets_received_error": 0,
                "packets_sent": 0,
                "port_id": 3,
            }, {
                "bytes_received": 9800,
                "bytes_sent": 6540,
                "duration": 150,
                "packets_internal_received": 0,
                "packets_internal_sent": 7650,
                "packets_received": 20,
                "packets_received_drop": 0,
                "packets_received_error": 0,
                "packets_sent": 0,
                "port_id": 2,
                "tenant_id": PORT_2_TENANT_ID,
                "uuid": PORT_2_ID
            }, {
                "bytes_received": 100,
                "bytes_sent": 840,
                "duration": 100,
                "packets_internal_received": 984,
                "packets_internal_sent": 7950,
                "packets_received": 9900,
                "packets_received_drop": 1500,
                "packets_received_error": 1000,
                "packets_sent": 7890,
                "port_id": 1,
                "tenant_id": PORT_1_TENANT_ID,
                "uuid": PORT_1_ID
            }],
            "table_counters": [{
                "flow_count": 90,
                "table_id": 10
            }, {
                "flow_count": 80,
                "table_id": 20
            }],
        }, {
            "packet_in_messages_received": 0,
            "packet_out_messages_sent": 0,
            "ports": 0,
            "flow_datapath_id": 55120148545555,
            "table_counters": [{
                "flow_count": 5,
                "table_id": 10
            }, {
                "flow_count": 3,
                "table_id": 20
            }],
        }]
    }

    def test_meter_switch(self):
        expected_data = [
            (1, "55120148545607", {
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
            (1, "55120148545555", {
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
        ]

        self._test_for_meter('switch', expected_data)

    def test_meter_switch_ports(self):
        expected_data = [
            (3, "55120148545607", {
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
            (0, "55120148545555", {
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
        ]

        self._test_for_meter('switch.ports', expected_data)

    def test_meter_switch_port(self):
        expected_data = [
            (1, "55120148545607:3", {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 3,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (1, '55120148545607:2', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 2,
                'neutron_port_id': PORT_2_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (1, '55120148545607:1', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 1,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port', expected_data)

    def test_meter_switch_port_uptime(self):
        expected_data = [
            (200, "55120148545607:3", {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 3,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (150, '55120148545607:2', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 2,
                'neutron_port_id': PORT_2_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (100, '55120148545607:1', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 1,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.uptime', expected_data)

    def test_meter_switch_port_receive_packets(self):
        expected_data = [
            (10, "55120148545607:3", {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 3,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (20, '55120148545607:2', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 2,
                'neutron_port_id': PORT_2_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (9900, '55120148545607:1', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 1,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.receive.packets', expected_data)

    def test_meter_switch_port_transmit_packets(self):
        expected_data = [
            (0, "55120148545607:3", {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 3,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (0, '55120148545607:2', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 2,
                'neutron_port_id': PORT_2_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (7890, '55120148545607:1', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 1,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.transmit.packets', expected_data)

    def test_meter_switch_port_receive_bytes(self):
        expected_data = [
            (0, "55120148545607:3", {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 3,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (9800, '55120148545607:2', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 2,
                'neutron_port_id': PORT_2_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (100, '55120148545607:1', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 1,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.receive.bytes', expected_data)

    def test_meter_switch_port_transmit_bytes(self):
        expected_data = [
            (512, "55120148545607:3", {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 3,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (6540, '55120148545607:2', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 2,
                'neutron_port_id': PORT_2_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (840, '55120148545607:1', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 1,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.transmit.bytes', expected_data)

    def test_meter_switch_port_receive_drops(self):
        expected_data = [
            (0, "55120148545607:3", {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 3,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (0, '55120148545607:2', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 2,
                'neutron_port_id': PORT_2_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (1500, '55120148545607:1', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 1,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.receive.drops', expected_data)

    def test_meter_switch_port_receive_errors(self):
        expected_data = [
            (0, "55120148545607:3", {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 3,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (0, '55120148545607:2', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 2,
                'neutron_port_id': PORT_2_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
            (1000, '55120148545607:1', {
                'controller': 'OpenDaylight_V2',
                'port_number_on_switch': 1,
                'neutron_port_id': PORT_1_ID,
                'switch': '55120148545607'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.port.receive.errors', expected_data)

    def test_meter_port(self):
        expected_data = [
            (1, str(PORT_2_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_2_TENANT_ID),
            (1, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port', expected_data)

    def test_meter_port_uptime(self):
        expected_data = [
            (150, str(PORT_2_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_2_TENANT_ID),
            (100, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.uptime', expected_data)

    def test_meter_port_receive_packets(self):
        expected_data = [
            (20, str(PORT_2_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_2_TENANT_ID),
            (9900, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.receive.packets', expected_data)

    def test_meter_port_transmit_packets(self):
        expected_data = [
            (0, str(PORT_2_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_2_TENANT_ID),
            (7890, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.transmit.packets', expected_data)

    def test_meter_port_receive_bytes(self):
        expected_data = [
            (9800, str(PORT_2_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_2_TENANT_ID),
            (100, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.receive.bytes', expected_data)

    def test_meter_port_transmit_bytes(self):
        expected_data = [
            (6540, str(PORT_2_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_2_TENANT_ID),
            (840, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.transmit.bytes', expected_data)

    def test_meter_port_receive_drops(self):
        expected_data = [
            (0, str(PORT_2_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_2_TENANT_ID),
            (1500, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.receive.drops', expected_data)

    def test_meter_port_receive_errors(self):
        expected_data = [
            (0, str(PORT_2_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_2_TENANT_ID),
            (1000, str(PORT_1_ID),
             {'controller': 'OpenDaylight_V2'},
             PORT_1_TENANT_ID),
        ]
        self._test_for_meter('port.receive.errors', expected_data)

    def test_meter_switch_table_active_entries(self):
        expected_data = [
            (90, "55120148545607:table:10", {
                'switch': '55120148545607',
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
            (80, "55120148545607:table:20", {
                'switch': '55120148545607',
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
            (5, "55120148545555:table:10", {
                'switch': '55120148545555',
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
            (3, "55120148545555:table:20", {
                'switch': '55120148545555',
                'controller': 'OpenDaylight_V2'
            }, ADMIN_ID),
        ]
        self._test_for_meter('switch.table.active.entries', expected_data)
