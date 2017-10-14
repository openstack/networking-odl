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

import os

from neutron.plugins.ml2.drivers import type_vxlan  # noqa
from neutron import privileged  # noqa
from neutron.tests import base as tests_base
from neutron.tests.common import helpers
from neutron.tests.unit.plugins.ml2 import test_plugin
from oslo_config import cfg

from networking_odl.common import config as odl_config
import networking_odl.db.models  # noqa


class TestODLFullStackBase(test_plugin.Ml2PluginV2TestCase):

    _mechanism_drivers = ['logger', 'opendaylight_v2']
    _extension_drivers = ['port_security']
    l3_plugin = 'networking_odl.l3.l3_odl_v2.OpenDaylightL3RouterPlugin'

    # this is stolen from neutron.tests.fullstack.base
    #
    # This is the directory from which infra fetches log files
    # for fullstack tests
    DEFAULT_LOG_DIR = os.path.join(helpers.get_test_log_path(),
                                   'dsvm-fullstack-logs')

    def setUp(self):
        # NOTE(yamahata):
        # When tox is using virtualenv and oslo.privsep is also installed
        # in system, sudo chooses system one.
        # However for privsep-helper to find python module in virtualenv
        # we need to use the on under .tox. So specify the full path
        # and preserve environmental variables.
        privsep_helper = "privsep-helper"
        if "VIRTUAL_ENV" in os.environ:
            privsep_helper = os.path.join(
                os.environ["VIRTUAL_ENV"], "bin", privsep_helper)
        cfg.CONF.set_override(
            "helper_command", "sudo --preserve-env " + privsep_helper,
            group="privsep")

        cfg.CONF.set_override('extension_drivers',
                              self._extension_drivers, group='ml2')
        cfg.CONF.set_override('tenant_network_types',
                              ['vxlan'], group='ml2')
        cfg.CONF.set_override('vni_ranges',
                              ['1:1000'], group='ml2_type_vxlan')

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
        odl_config.cfg.CONF.set_override('odl_features',
                                         ['no-feature'],
                                         group='ml2_odl')
        super(TestODLFullStackBase, self).setUp()
        tests_base.setup_test_logging(
            cfg.CONF, self.DEFAULT_LOG_DIR, '%s.txt' % self.get_name())

    def get_name(self):
        class_name, test_name = self.id().split(".")[-2:]
        return "%s.%s" % (class_name, test_name)
