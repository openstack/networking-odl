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

import mock
from oslo_config import fixture as config_fixture
from oslo_serialization import jsonutils
import requests
import websocket

from networking_odl.common.client import OpenDaylightRestClient as odl_client
from networking_odl.common import websocket_client as wsc
from networking_odl.tests import base


class TestWebsocketClient(base.DietTestCase):
    """Test class for Websocket Client."""

    FAKE_WEBSOCKET_STREAM_NAME_DATA = {
        'output': {
            'stream-name': 'data-change-event-subscription/neutron:neutron/'
            'neutron:hostconfigs/datastore=OPERATIONAL/scope=SUBTREE'
        }}

    INVALID_WEBSOCKET_STREAM_NAME_DATA = {
        'outputs': {
            'stream-name': 'data-change-event-subscription/neutron:neutron/'
            'neutron:hostconfigs/datastore=OPERATIONAL/scope=SUBTREE'
        }}

    FAKE_WEBSOCKET_SUBS_DATA = {
        'location': 'ws://localhost:8185/data-change-event-subscription/'
        'neutron:neutron/neutron:hostconfigs/datastore=OPERATIONAL'
        '/scope=SUBTREE'}

    ODL_URI = "http://localhost:8080/"

    WEBSOCKET_URI = (
        "ws://localhost:8185/" +
        "data-change-event-subscription/neutron:neutron/" +
        "neutron:hostconfigs/datastore=OPERATIONAL/scope=SUBTREE")

    WEBSOCKET_SSL_URI = (
        "wss://localhost:8185/" +
        "data-change-event-subscription/neutron:neutron/" +
        "neutron:hostconfigs/datastore=OPERATIONAL/scope=SUBTREE")

    mock_callback_handler = mock.MagicMock()

    def setUp(self):
        """Setup test."""
        self.useFixture(base.OpenDaylightRestClientFixture())
        mock.patch.object(wsc.OpenDaylightWebsocketClient,
                          'start_odl_websocket_thread').start()
        self.cfg = self.useFixture(config_fixture.Config())
        super(TestWebsocketClient, self).setUp()

        self.mgr = wsc.OpenDaylightWebsocketClient.odl_create_websocket(
            TestWebsocketClient.ODL_URI,
            "restconf/operational/neutron:neutron/hostconfigs",
            wsc.ODL_OPERATIONAL_DATASTORE, wsc.ODL_NOTIFICATION_SCOPE_SUBTREE,
            TestWebsocketClient.mock_callback_handler
        )

    def _get_raised_response(self, status_code):
        response = requests.Response()
        response.status_code = status_code
        return response

    @classmethod
    def _get_mock_request_response(cls, status_code):
        response = mock.Mock(status_code=status_code)
        side_effect = None
        # NOTE(rajivk): requests.codes.bad_request constant value is 400,
        # so it filters requests where client(4XX) or server(5XX) has erred.
        if status_code >= requests.codes.bad_request:
            side_effect = requests.exceptions.HTTPError()

        response.raise_for_status = mock.Mock(side_effect=side_effect)
        return response

    @mock.patch.object(odl_client, 'sendjson')
    def test_subscribe_websocket_sendjson(self, mocked_sendjson):
        request_response = self._get_raised_response(
            requests.codes.unauthorized)

        mocked_sendjson.return_value = request_response
        stream_url = self.mgr._subscribe_websocket()
        self.assertIsNone(stream_url)

        request_response = self._get_raised_response(
            requests.codes.bad_request)

        mocked_sendjson.return_value = request_response
        self.assertRaises(ValueError, self.mgr._subscribe_websocket)

        request_response = self._get_mock_request_response(requests.codes.ok)
        request_response.json = mock.Mock(
            return_value=(TestWebsocketClient.
                          INVALID_WEBSOCKET_STREAM_NAME_DATA))
        mocked_sendjson.return_value = request_response
        self.assertRaises(ValueError, self.mgr._subscribe_websocket)

        request_response = self._get_mock_request_response(requests.codes.ok)
        request_response.json = mock.Mock(return_value={""})
        mocked_sendjson.return_value = request_response
        self.assertIsNone(self.mgr._subscribe_websocket())

    @mock.patch.object(odl_client, 'get')
    def test_subscribe_websocket_get(self, mocked_get):
        request_response = self._get_raised_response(requests.codes.not_found)
        mocked_get.return_value = request_response
        self.assertRaises(ValueError, self.mgr._subscribe_websocket)

        request_response = self._get_raised_response(
            requests.codes.bad_request)

        mocked_get.return_value = request_response
        stream_url = self.mgr._subscribe_websocket()
        self.assertIsNone(stream_url)

        request_response = self._get_raised_response(
            requests.codes.unauthorized)

        mocked_get.return_value = request_response
        stream_url = self.mgr._subscribe_websocket()
        self.assertIsNone(stream_url)

    @mock.patch.object(odl_client, 'sendjson')
    @mock.patch.object(odl_client, 'get')
    def test_subscribe_websocket(self, mocked_get, mocked_sendjson):
        request_response = self._get_mock_request_response(requests.codes.ok)
        request_response.json = mock.Mock(
            return_value=TestWebsocketClient.FAKE_WEBSOCKET_STREAM_NAME_DATA)
        mocked_sendjson.return_value = request_response

        request_response = self._get_mock_request_response(requests.codes.ok)
        request_response.headers = TestWebsocketClient.FAKE_WEBSOCKET_SUBS_DATA
        mocked_get.return_value = request_response
        stream_url = self.mgr._subscribe_websocket()

        self.assertEqual(TestWebsocketClient.WEBSOCKET_URI, stream_url)

    @mock.patch.object(websocket, 'create_connection')
    def test_create_connection(self, mock_create_connection):
        mock_create_connection.return_value = None
        return_value = self.mgr._socket_create_connection("localhost")
        self.assertIsNone(return_value)

    @mock.patch.object(websocket, 'create_connection',
                       side_effect=Exception("something went wrong"))
    def test_create_connection_handles_exception(self, mock_create_connection):
        self.assertIsNone(self.mgr._socket_create_connection("localhost"))

    def test_websocket_connect(self):
        self.mgr._subscribe_websocket = mock.MagicMock(
            return_value=TestWebsocketClient.WEBSOCKET_URI)
        self.mgr._socket_create_connection = mock.MagicMock(return_value=True)
        self.mgr._connect_ws()
        self.mgr._socket_create_connection.assert_called_with(
            TestWebsocketClient.WEBSOCKET_URI)

    def test_websocket_connect_ssl(self):
        self.mgr._subscribe_websocket = mock.MagicMock(
            return_value=TestWebsocketClient.WEBSOCKET_SSL_URI)
        self.mgr._socket_create_connection = mock.MagicMock(return_value=True)
        self.mgr._connect_ws()
        self.mgr._socket_create_connection.assert_called_with(
            TestWebsocketClient.WEBSOCKET_SSL_URI)

    def test_websocket_connect_ssl_negative_uri(self):
        self.mgr._subscribe_websocket = mock.MagicMock(
            return_value=TestWebsocketClient.WEBSOCKET_URI)
        self.mgr._socket_create_connection = mock.MagicMock(return_value=True)
        self.mgr.odl_rest_client.url = self.mgr.odl_rest_client.url.replace(
            'http:', 'https:')
        self.mgr._connect_ws()
        self.mgr._socket_create_connection.assert_called_with(
            TestWebsocketClient.WEBSOCKET_SSL_URI)

    def test_run_websocket_thread(self):
        self.mgr._connect_ws = mock.MagicMock(return_value=None)
        self.cfg.config(restconf_poll_interval=0, group='ml2_odl')
        self.mgr.run_websocket_thread(True)
        assert self.mgr._connect_ws.call_count == 1

        self.mgr.set_exit_flag(False)
        self.mgr._connect_ws = mock.MagicMock(return_value=1)
        with mock.patch.object(wsc, 'LOG') as mock_log:
            self.mgr.run_websocket_thread(True)
            self.assertTrue(mock_log.error.called)

        self.mgr.set_exit_flag(False)
        ws = mock.MagicMock()
        ws.recv.return_value = None
        self.mgr._connect_ws = mock.MagicMock(return_value=ws)
        self.mgr._close_ws = mock.MagicMock(return_value=None)
        with mock.patch.object(wsc, 'LOG') as mock_log:
            self.mgr.run_websocket_thread(True)
            self.assertTrue(mock_log.warning.called)

        self.mgr.set_exit_flag(False)
        ws = mock.MagicMock()
        ws.recv.return_value = "Test Data"
        self.mgr._connect_ws = mock.MagicMock(return_value=ws)
        self.mgr._close_ws = mock.MagicMock(return_value=None)
        self.mgr.run_websocket_thread(True)
        TestWebsocketClient.mock_callback_handler.assert_called_once()


class TestEventDataParser(base.DietTestCase):
    """Test class for Websocket Client."""

    # test data port status payload
    sample_port_status_payload = """{"notification":
        {"xmlns":"urn:ietf:params:xml:ns:netconf:notification:1.0",
         "data-changed-notification": { "xmlns":
             "urn:opendaylight:params:xml:ns:yang:controller:md:sal:remote",
             "data-change-event":
                 [{"path":
                "/neutron:neutron/neutron:ports/neutron:port\
                [neutron:uuid='a51e439f-4d02-4e76-9b0d-08f6c08855dd']\
                /neutron:uuid",
                "data":{"uuid":{"xmlns":"urn:opendaylight:neutron",
                        "content":"a51e439f-4d02-4e76-9b0d-08f6c08855dd"}},
                "operation":"created"},
                {"path":
                "/neutron:neutron/neutron:ports/neutron:port\
                [neutron:uuid='a51e439f-4d02-4e76-9b0d-08f6c08855dd']\
                /neutron:status",
                "data":{"status":{"xmlns":"urn:opendaylight:neutron",
                        "content":"ACTIVE"}},
                 "operation":"created"}
                  ]},
            "eventTime":"2017-03-23T09:28:55.379-07:00"}}"""

    sample_port_status_payload_one_item = """{"notification":
        {"xmlns": "urn:ietf:params:xml:ns:netconf:notification:1.0",
        "data-changed-notification": {
         "data-change-event": {
            "data": { "status": {
                        "content": "ACTIVE",
                        "xmlns": "urn:opendaylight:neutron"
            }},
            "operation": "updated",
            "path": "/neutron:neutron/neutron:ports/neutron:port\
            [neutron:uuid='d6e6335d-9568-4949-aef1-4107e34c5f28']\
            /neutron:status"
            },
            "xmlns": "urn:opendaylight:params:xml:ns:yang:controller:md:\
            sal:remote"
        },
        "eventTime": "2017-02-22T02:27:32+02:00" }}"""

    def setUp(self):
        """Setup test."""
        super(TestEventDataParser, self).setUp()

    def test_get_item_port_status_payload(self):
        sample = jsonutils.loads(self.sample_port_status_payload)
        expected_events = (sample
                           [wsc.EventDataParser.NOTIFICATION_TAG]
                           [wsc.EventDataParser.DC_NOTIFICATION_TAG]
                           [wsc.EventDataParser.DC_EVENT_TAG])
        event_0 = expected_events[0]
        event = wsc.EventDataParser.get_item(self.sample_port_status_payload)
        operation, path, data = next(event).get_fields()

        self.assertEqual(event_0.get('operation'), operation)
        self.assertEqual(event_0.get('path'), path)
        self.assertEqual(event_0.get('data'), data)

        uuid = wsc.EventDataParser.extract_field(path, "neutron:uuid")
        self.assertEqual("'a51e439f-4d02-4e76-9b0d-08f6c08855dd'", uuid)

        uuid = wsc.EventDataParser.extract_field(path, "invalidkey")
        self.assertIsNone(uuid)

    def test_get_item_port_status_payload_one_item(self):
        sample = jsonutils.loads(self.sample_port_status_payload_one_item)
        expected_events = (sample
                           [wsc.EventDataParser.NOTIFICATION_TAG]
                           [wsc.EventDataParser.DC_NOTIFICATION_TAG]
                           [wsc.EventDataParser.DC_EVENT_TAG])
        event = (wsc.EventDataParser.
                 get_item(self.sample_port_status_payload_one_item))
        operation, path, data = next(event).get_fields()

        self.assertEqual(expected_events.get('operation'), operation)
        self.assertEqual(expected_events.get('path'), path)
        self.assertEqual(expected_events.get('data'), data)

        uuid = wsc.EventDataParser.extract_field(path, "neutron:uuid")
        self.assertEqual("'d6e6335d-9568-4949-aef1-4107e34c5f28'", uuid)
