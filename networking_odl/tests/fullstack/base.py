# Copyright (c) 2016 OpenStack Foundation
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

from neutron.plugins.ml2 import config
from neutron.plugins.ml2.drivers import type_vxlan  # noqa
from neutron.tests.unit.plugins.ml2 import test_plugin

from networking_odl.common import config as odl_config


class TestODLFullStackBase(test_plugin.Ml2PluginV2TestCase):

    _mechanism_drivers = ['logger', 'opendaylight']
    _extension_drivers = ['port_security']

    def setUp(self):
        config.cfg.CONF.set_override('extension_drivers',
                                     self._extension_drivers,
                                     group='ml2')
        config.cfg.CONF.set_override('tenant_network_types',
                                     ['vxlan'],
                                     group='ml2')
        config.cfg.CONF.set_override('vni_ranges',
                                     ['1:1000'],
                                     group='ml2_type_vxlan')

        odl_url = 'http://127.0.0.1:8087/controller/nb/v2/neutron'
        odl_config.cfg.CONF.set_override('url',
                                         odl_url,
                                         group='ml2_odl')
        odl_config.cfg.CONF.set_override('username',
                                         'admin',
                                         group='ml2_odl')
        odl_config.cfg.CONF.set_override('password',
                                         'admin',
                                         group='ml2_odl')
        odl_config.cfg.CONF.set_override('port_binding_controller',
                                         'legacy-port-binding',
                                         group='ml2_odl')

        super(TestODLFullStackBase, self).setUp()
