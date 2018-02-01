# Copyright (c) 2017 OpenStack Foundation
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
import testscenarios

from neutron_lib import constants as n_const
from neutron_lib.plugins import directory

from networking_odl.dhcp import odl_dhcp_driver_base as driver_base
from networking_odl.ml2 import mech_driver_v2
from networking_odl.tests import base as odl_base
from networking_odl.tests.unit import base_v2

from oslo_config import cfg
from oslo_utils import uuidutils

# Required to generate tests from scenarios. Not compatible with nose.
load_tests = testscenarios.load_tests_apply_scenarios
ODL_TENANT_ID = uuidutils.generate_uuid()
cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')


class OdlDhcpDriverTestBase(base_v2.OpenDaylightConfigBase):

    def setUp(self):
        self.useFixture(odl_base.OpenDaylightFeaturesFixture())
        self.useFixture(odl_base.OpenDaylightJournalThreadFixture())
        self.useFixture(odl_base.OpenDaylightPseudoAgentPrePopulateFixture())
        super(OdlDhcpDriverTestBase, self).setUp()

    def get_network_and_subnet_context(self, cidr, dhcp_flag, create_subnet,
                                       create_network, ipv4=True):
        data = {}
        network_id = uuidutils.generate_uuid()
        subnet_id = uuidutils.generate_uuid()
        plugin = directory.get_plugin()
        data['network_id'] = network_id
        data['subnet_id'] = subnet_id
        data['context'] = self.context
        data['plugin'] = plugin
        network, network_context = \
            self.get_network_context(network_id, create_network, ipv4)
        if create_network:
            data['network_context'] = network_context
        data['network'] = network
        subnet, subnet_context = \
            self.get_subnet_context(network_id, subnet_id, cidr,
                                    dhcp_flag, create_subnet, ipv4)
        if create_subnet:
            data['subnet_context'] = subnet_context
        data['subnet'] = subnet
        return data

    def get_subnet_context(self, network_id, subnet_id, cidr,
                           dhcp_flag, create_subnet, ipv4=True):
        if ipv4:
            index = cidr.rfind('.') + 1
            ip_range = cidr[:index]
            cidr_end = ip_range + str(254)
            ipv6_ramode = None
            ipv6_addmode = None
            ipversion = 4
        else:
            index = cidr.rfind(':') + 1
            ip_range = cidr[:index]
            cidr_end = cidr[:index - 1] + 'ffff:ffff:ffff:fffe'
            ipv6_ramode = 'slaac'
            ipv6_addmode = 'slaac'
            ipversion = 6
        current = {'ipv6_ra_mode': ipv6_ramode,
                   'allocation_pools': [{'start': ip_range + str(2),
                                         'end': cidr_end}],
                   'host_routes': [],
                   'ipv6_address_mode': ipv6_addmode,
                   'cidr': cidr,
                   'id': subnet_id,
                   'name': '',
                   'enable_dhcp': dhcp_flag,
                   'network_id': network_id,
                   'tenant_id': ODL_TENANT_ID,
                   'project_id': ODL_TENANT_ID,
                   'dns_nameservers': [],
                   'gateway_ip': ip_range + str(1),
                   'ip_version': ipversion,
                   'shared': False}
        subnet = {'subnet': AttributeDict(current)}
        if create_subnet:
            plugin = directory.get_plugin()
            result, subnet_context = plugin._create_subnet_db(self.context,
                                                              subnet)
            return subnet, subnet_context
        else:
            return subnet

    def get_network_context(self, network_id, create_network, ipv4=True):
        netwrk = 'netv4'
        if not ipv4:
            netwrk = 'netv6'
        current = {'status': 'ACTIVE',
                   'subnets': [],
                   'name': netwrk,
                   'provider:physical_network': None,
                   'admin_state_up': True,
                   'tenant_id': ODL_TENANT_ID,
                   'project_id': ODL_TENANT_ID,
                   'provider:network_type': 'local',
                   'router:external': False,
                   'shared': False,
                   'id': network_id,
                   'provider:segmentation_id': None}
        network = {'network': AttributeDict(current)}
        if create_network:
            plugin = directory.get_plugin()
            result, network_context = plugin._create_network_db(
                self.context, network)
            return [network, network_context]
        return network

    def get_port_id(self, plugin, plugin_context, network_id, subnet_id):

        device_id = driver_base.OPENDAYLIGHT_DEVICE_ID + '-' + subnet_id
        filters = {
            'network_id': [network_id],
            'device_id': [device_id],
            'device_owner': [n_const.DEVICE_OWNER_DHCP]
        }
        ports = plugin.get_ports(plugin_context, filters=filters)
        if ports:
            port = ports[0]
            return port['id']


class OdlDhcpDriverBaseTestCase(OdlDhcpDriverTestBase):

    def setUp(self):
        super(OdlDhcpDriverBaseTestCase, self).setUp()

    def test_dhcp_driver_not_loaded_without_flag(self):
        mech = mech_driver_v2.OpenDaylightMechanismDriver()
        mech.initialize()
        args = [mech, 'dhcp_driver']
        self.assertRaises(AttributeError, getattr, *args)

    def test_dhcp_port_create(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()

        data = self.get_network_and_subnet_context('10.0.10.0/24', True, True,
                                                   True)

        dhcp_driver.create_or_delete_dhcp_port(data['subnet_context'])

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNotNone(port)

    def test_dhcp_port_create_v6network(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()

        data = self.get_network_and_subnet_context('2001:db8:abcd:0012::0/64',
                                                   True, True, True, False)
        dhcp_driver.create_or_delete_dhcp_port(data['subnet_context'])

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNone(port)

    def test_dhcp_create_without_dhcp_flag(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()
        data = self.get_network_and_subnet_context('10.0.20.0/24', False, True,
                                                   True)

        dhcp_driver.create_or_delete_dhcp_port(data['subnet_context'])

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNone(port)

    def test_dhcp_port_create_with_multiple_create_request(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()
        data = self.get_network_and_subnet_context('10.0.30.0/24', True, True,
                                                   True)

        dhcp_driver.create_or_delete_dhcp_port(data['subnet_context'])
        dhcp_driver.create_or_delete_dhcp_port(data['subnet_context'])
        # If there are multiple ports will one_or_none wiill throw error
        # MultipleResultsFound
        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNotNone(port)

    def test_dhcp_update_from_disable_to_enable(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()
        data = self.get_network_and_subnet_context('10.0.40.0/24', False, True,
                                                   True)
        subnet_context = data['subnet_context']
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        subnet_context.current['enable_dhcp'] = True
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNotNone(port)

    def test_dhcp_update_from_enable_to_enable(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()
        data = self.get_network_and_subnet_context('10.0.50.0/24', True, True,
                                                   True)
        subnet_context = data['subnet_context']
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        subnet_context.current['enable_dhcp'] = True
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNotNone(port)

    def test_dhcp_update_from_enable_to_disable(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()
        data = self.get_network_and_subnet_context('10.0.60.0/24', True, True,
                                                   True)
        subnet_context = data['subnet_context']
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        subnet_context.current['enable_dhcp'] = False
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNone(port)

    def test_dhcp_update_from_disable_to_disable(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()
        data = self.get_network_and_subnet_context('10.0.70.0/24', False, True,
                                                   True)
        subnet_context = data['subnet_context']
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        subnet_context.current['enable_dhcp'] = False
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)

        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNone(port)

    def test_dhcp_delete_when_dhcp_enabled(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()
        data = self.get_network_and_subnet_context('10.0.80.0/24', True, True,
                                                   True)
        subnet_context = data['subnet_context']
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        subnet_context.current['enable_dhcp'] = False
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNone(port)

    def test_dhcp_delete_when_dhcp_delete(self):
        dhcp_driver = driver_base.OdlDhcpDriverBase()
        data = self.get_network_and_subnet_context('10.0.90.0/24', False, True,
                                                   True)
        subnet_context = data['subnet_context']
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        dhcp_driver.create_or_delete_dhcp_port(subnet_context)
        port = self.get_port_id(data['plugin'],
                                data['context'],
                                data['network_id'],
                                data['subnet_id'])
        self.assertIsNone(port)


class AttributeDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttributeDict, self).__init__(*args, **kwargs)
        self.__dict__ = self
