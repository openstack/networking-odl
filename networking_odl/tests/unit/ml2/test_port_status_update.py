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

import re
import threading

import mock

from networking_odl.common.client import OpenDaylightRestClient
from networking_odl.common import websocket_client as odl_ws_client
from networking_odl.common.websocket_client import OpenDaylightWebsocketClient
from networking_odl.ml2.port_status_update import OdlPortStatusUpdate
from networking_odl.tests import base
from neutron.db import provisioning_blocks
import neutron_lib.context
import neutron_lib.plugins.directory


class TestOdlPortStatusUpdate(base.DietTestCase):

    WEBSOCK_NOTIFICATION = re.sub(r'\s*', '', """
        {
            "notification": {
                "data-changed-notification": {
                    "data-change-event": {
                        "data": {
                            "status": {
                                "content": "ACTIVE",
                                "xmlns": "urn:opendaylight:neutron"
                            }
                        },
                        "operation": "updated",
                        "path":
                        "/neutron:neutron/neutron:ports/neutron:port[
                        neutron:uuid='d6e6335d-9568-4949-aef1-4107e34c5f28']
                        /neutron:status"
                    },
                    "xmlns":
                "urn:opendaylight:params:xml:ns:yang:controller:md:sal:remote"
                },
                "eventTime": "2017-02-22T02:27:32+02:00",
                "xmlns": "urn:ietf:params:xml:ns:netconf:notification:1.0"
            }
        }""")

    def setUp(self):
        self.useFixture(base.OpenDaylightFeaturesFixture())
        self.mock_ws_client = mock.patch.object(
            OpenDaylightWebsocketClient, 'odl_create_websocket')
        super(TestOdlPortStatusUpdate, self).setUp()

    def test_object_create(self):
        OdlPortStatusUpdate()

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    def test_websock_recv(self, mocked_provisioning_complete):
        updater = OdlPortStatusUpdate()
        updater._process_websocket_recv(self.WEBSOCK_NOTIFICATION, False)
        mocked_provisioning_complete.assert_called_once()
        self.assertEqual(mocked_provisioning_complete.call_args[0][1],
                         'd6e6335d-9568-4949-aef1-4107e34c5f28')

    @mock.patch.object(provisioning_blocks, 'provisioning_complete')
    @mock.patch.object(neutron_lib.context, 'get_admin_context')
    @mock.patch.object(OpenDaylightRestClient, 'get')
    @mock.patch.object(neutron_lib.plugins.directory, 'get_plugin')
    def test_pull_missed_statuses(self, mocked_get_plugin, mocked_get, ac, pc):
        uuid = 'd6e6335d-9568-4949-aef1-4107e34c5f28'
        plugin = mock.MagicMock()
        plugin.get_ports = mock.MagicMock(return_value=[{'id': uuid}])
        mocked_get_plugin.return_value = plugin

        updater = OdlPortStatusUpdate()
        updater._pull_missed_statuses()

        mocked_get.assert_called_with(uuid)

    @mock.patch.object(threading, 'Thread')
    def test_process_websocket_reconnect(self, mocked_thread):
        updater = OdlPortStatusUpdate()
        updater._process_websocket_reconnect(
            odl_ws_client.ODL_WEBSOCKET_CONNECTED)
        mocked_thread.assert_called()
        mocked_thread.return_value.start.assert_called()
