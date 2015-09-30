# Copyright (c) 2015 Intel Inc.
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

import mock

from networking_odl.common import lightweight_testing as lwt

from neutron.tests import base


class LightweightTestingTestCase(base.DietTestCase):

    def test_create_client_with_lwt_enabled(self):
        """Have to do the importation here, otherwise there will be a loop"""
        from networking_odl.common import client as odl_client
        odl_client.cfg.CONF.set_override('enable_lightweight_testing',
                                         True, 'ml2_odl')
        # DietTestCase does not automatically cleans configuration overrides
        self.addCleanup(odl_client.cfg.CONF.reset)

        client = odl_client.OpenDaylightRestClient.create_client()
        self.assertIsInstance(client, lwt.OpenDaylightLwtClient)

    def test_create_client_with_lwt_disabled(self):
        """Have to do the importation here, otherwise there will be a loop"""
        from networking_odl.common import client as odl_client
        odl_client.cfg.CONF.set_override('enable_lightweight_testing',
                                         False, 'ml2_odl')
        # DietTestCase does not automatically cleans configuration overrides
        self.addCleanup(odl_client.cfg.CONF.reset)

        client = odl_client.OpenDaylightRestClient.create_client()
        self.assertIsInstance(client, odl_client.OpenDaylightRestClient)

    @mock.patch.dict(lwt.OpenDaylightLwtClient.lwt_dict,
                     {'networks': {}}, clear=True)
    def test_post_single_resource(self):
        client = lwt.OpenDaylightLwtClient.create_client()
        fake_network1 = {'id': 'fakeid1', 'name': 'fake_network1'}
        obj = {'networks': fake_network1}
        response = client.sendjson('post', 'networks', obj)
        self.assertEqual(lwt.NO_CONTENT, response.status_code)
        lwt_dict = lwt.OpenDaylightLwtClient.lwt_dict
        self.assertEqual(lwt_dict['networks']['fakeid1'],
                         fake_network1)

    @mock.patch.dict(lwt.OpenDaylightLwtClient.lwt_dict,
                     {'networks': {}}, clear=True)
    def test_post_multiple_resources(self):
        client = lwt.OpenDaylightLwtClient.create_client()
        fake_network1 = {'id': 'fakeid1', 'name': 'fake_network1'}
        fake_network2 = {'id': 'fakeid2', 'name': 'fake_network2'}
        obj = {'networks': [fake_network1, fake_network2]}
        response = client.sendjson('post', 'networks', obj)
        self.assertEqual(lwt.NO_CONTENT, response.status_code)
        lwt_dict = lwt.OpenDaylightLwtClient.lwt_dict
        self.assertEqual(lwt_dict['networks']['fakeid1'],
                         fake_network1)
        self.assertEqual(lwt_dict['networks']['fakeid2'],
                         fake_network2)

    @mock.patch.dict(lwt.OpenDaylightLwtClient.lwt_dict,
                     {'ports': {'fakeid1': {'id': 'fakeid1',
                                            'name': 'fake_port1'}}},
                     clear=True)
    def test_get_single_resource(self):
        client = lwt.OpenDaylightLwtClient.create_client()
        url_path = 'ports/fakeid1'
        response = client.sendjson('get', url_path, None)
        self.assertEqual(lwt.OK, response.status_code)
        res = response.json()
        # For single resource, the return value is a dict
        self.assertEqual(res['port']['name'], 'fake_port1')

    @mock.patch.dict(lwt.OpenDaylightLwtClient.lwt_dict,
                     {'ports': {'fakeid1': {'id': 'fakeid1',
                                            'name': 'fake_port1'},
                                'fakeid2': {'id': 'fakeid2',
                                            'name': 'fake_port2'}}},
                     clear=True)
    def test_get_multiple_resources(self):
        client = lwt.OpenDaylightLwtClient.create_client()
        url_path = 'ports/'
        response = client.sendjson('get', url_path, None)
        self.assertEqual(lwt.OK, response.status_code)
        res = response.json()
        for port in res:
            self.assertIn(port['port']['name'],
                          ['fake_port1', 'fake_port2'])

    @mock.patch.dict(lwt.OpenDaylightLwtClient.lwt_dict,
                     {'subnets': {'fakeid1': {'id': 'fakeid1',
                                              'name': 'fake_subnet1'}}},
                     clear=True)
    def test_put_single_resource(self):
        client = lwt.OpenDaylightLwtClient.create_client()
        changed = {'id': 'fakeid1', 'name': 'fake_subnet1_changed'}
        obj = {'subnets': changed}

        url_path = 'subnets/fakeid1'
        response = client.sendjson('put', url_path, obj)
        self.assertEqual(lwt.NO_CONTENT, response.status_code)
        lwt_dict = lwt.OpenDaylightLwtClient.lwt_dict
        self.assertEqual('fake_subnet1_changed',
                         lwt_dict['subnets']['fakeid1']['name'])

        """Check the client does not change the parameter"""
        self.assertEqual('fakeid1', changed['id'])
        self.assertEqual('fake_subnet1_changed', changed['name'])

    @mock.patch.dict(lwt.OpenDaylightLwtClient.lwt_dict,
                     {'subnets': {'fakeid1': {'id': 'fakeid1',
                                              'name': 'fake_subnet1'},
                                  'fakeid2': {'id': 'fakeid2',
                                              'name': 'fake_subnet2'}}},
                     clear=True)
    def test_put_multiple_resources(self):
        client = lwt.OpenDaylightLwtClient.create_client()
        changed1 = {'id': 'fakeid1', 'name': 'fake_subnet1_changed'}
        changed2 = {'id': 'fakeid2', 'name': 'fake_subnet2_changed'}
        obj = {'subnets': [changed1, changed2]}

        url_path = 'subnets/'
        response = client.sendjson('put', url_path, obj)
        self.assertEqual(lwt.NO_CONTENT, response.status_code)
        lwt_dict = lwt.OpenDaylightLwtClient.lwt_dict
        self.assertEqual('fake_subnet1_changed',
                         lwt_dict['subnets']['fakeid1']['name'])
        self.assertEqual('fake_subnet2_changed',
                         lwt_dict['subnets']['fakeid2']['name'])

    @mock.patch.dict(lwt.OpenDaylightLwtClient.lwt_dict,
                     {'networks': {'fakeid1': {'id': 'fakeid1',
                                               'name': 'fake_network1'}}},
                     clear=True)
    def test_delete_single_resource(self):
        client = lwt.OpenDaylightLwtClient.create_client()
        url_path = 'networks/fakeid1'
        response = client.sendjson('delete', url_path, None)
        self.assertEqual(lwt.NO_CONTENT, response.status_code)
        lwt_dict = lwt.OpenDaylightLwtClient.lwt_dict
        network = lwt_dict['networks'].get('fakeid1')
        self.assertEqual(None, network)

    @mock.patch.dict(lwt.OpenDaylightLwtClient.lwt_dict,
                     {'networks': {'fakeid1': {'id': 'fakeid1',
                                               'name': 'fake_network1'},
                                   'fakeid2': {'id': 'fakeid2',
                                               'name': 'fake_network2'}}},
                     clear=True)
    def test_delete_multiple_resources(self):
        client = lwt.OpenDaylightLwtClient.create_client()
        network1 = {'id': 'fakeid1'}
        network2 = {'id': 'fakeid2'}
        obj = {'networks': [network1, network2]}
        response = client.sendjson('delete', 'networks/', obj)
        self.assertEqual(lwt.NO_CONTENT, response.status_code)
        lwt_dict = lwt.OpenDaylightLwtClient.lwt_dict
        network = lwt_dict['networks'].get('fakeid1')
        self.assertEqual(None, network)
        network = lwt_dict['networks'].get('fakeid2')
        self.assertEqual(None, network)
