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
import ssl
import threading
import time

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import excutils
from requests import codes
from requests import exceptions
import websocket

from networking_odl._i18n import _
from networking_odl.common import client as odl_client


cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = log.getLogger(__name__)

ODL_OPERATIONAL_DATASTORE = "OPERATIONAL"
ODL_CONFIGURATION_DATASTORE = "CONFIGURATION"
ODL_NOTIFICATION_SCOPE_BASE = "BASE"
ODL_NOTIFICATION_SCOPE_ONE = "ONE"
ODL_NOTIFICATION_SCOPE_SUBTREE = "SUBTREE"

ODL_WEBSOCKET_DISCONNECTED = "ODL_WEBSOCKET_DISCONNECTED"
ODL_WEBSOCKET_CONNECTING = "ODL_WEBSOCKET_CONNECTING"
ODL_WEBSOCKET_CONNECTED = "ODL_WEBSOCKET_CONNECTED"


class OpenDaylightWebsocketClient(object):
    """Thread for the OpenDaylight Websocket """

    def __init__(self, odl_rest_client, path, datastore, scope, leaf_node_only,
                 packet_handler, timeout, status_cb=None):
        self.odl_rest_client = odl_rest_client
        self.path = path
        self.datastore = datastore
        self.scope = scope
        self.leaf_node_only = leaf_node_only
        self.packet_handler = packet_handler
        self.timeout = timeout
        self.exit_websocket_thread = False
        self.status_cb = status_cb
        self.current_status = ODL_WEBSOCKET_DISCONNECTED
        self._odl_sync_thread = self.start_odl_websocket_thread()

    @classmethod
    def odl_create_websocket(cls, odl_url, path, datastore, scope,
                             packet_handler, status_cb=None,
                             leaf_node_only=False):
        """Create a websocket connection with ODL.

                This method will create a websocket client based on path,
                datastore and scope params. On data recv from websocket
                packet_handler callback is called. status_cb callback can be
                provided if notifications are requried for socket status
                changes
        """

        if odl_url is None:
            LOG.error("invalid odl url", exc_info=True)
            raise ValueError(_("Invalid ODL URL"))

        odl_rest_client = odl_client.OpenDaylightRestClient.create_client(
            odl_url)
        return cls(
            odl_rest_client, path, datastore, scope, leaf_node_only,
            packet_handler, cfg.CONF.ml2_odl.timeout, status_cb
        )

    def start_odl_websocket_thread(self):
        # Start the websocket thread
        LOG.debug("starting a new websocket thread")
        odl_websocket_thread = threading.Thread(
            name='websocket',
            target=self.run_websocket_thread)
        odl_websocket_thread.start()
        return odl_websocket_thread

    def set_exit_flag(self, value=True):
        # set flag to exit
        self.exit_websocket_thread = value

    def run_websocket_thread(self, exit_after_run=False):
        # TBD connections are persistent so there is really no way to know
        # when it is a "first connection". We need to wait for the
        # dis/reconnect logic to be able to know this
        first_connection = True
        ws = None
        while not self.exit_websocket_thread:
            if exit_after_run:
                # Permanently waiting thread model breaks unit tests
                # Adding this arg to exit after one run for unit tests
                self.set_exit_flag()
            # connect if necessary
            if ws is None:
                try:
                    ws = self._connect_ws()
                except ValueError:
                    LOG.error("websocket irrecoverable error ")
                    return
                if ws is None:
                    time.sleep(cfg.CONF.ml2_odl.restconf_poll_interval)
                    continue
            # read off the websocket
            try:
                data = ws.recv()
                if not data:
                    LOG.warning("websocket received 0 bytes")
                    continue
            except websocket.WebSocketTimeoutException:
                continue
            except ssl.SSLError as e:
                message = e.args[0] if e.args else None
                # TODO(trozet): Workaround due to SSL Timeout not being caught
                # in websocket-client lib (issue 387).  Remove when fixed in
                # websocket-client lib.
                if message and 'timed out' in message:
                    continue
                else:
                    LOG.error("SSL websocket unexpected exception, "
                              "closing and restarting...", exc_info=True)
                    # TODO(rsood): Websocket reconnect can cause race
                    # conditions
                    self._close_ws(ws)
                    ws = None
                    continue
            except websocket.WebSocketConnectionClosedException:
                # per websocket-client, "If remote host closed the connection
                # or some network error happened"
                LOG.warning("websocket connection closed or IO error",
                            exc_info=True)
                self._close_ws(ws)
                ws = None
                continue
            except Exception:
                # Connection closed trigger reconnection
                LOG.error("websocket unexpected exception, "
                          "closing and restarting...", exc_info=True)
                # TODO(rsood): Websocket reconnect can cause race conditions
                self._close_ws(ws)
                ws = None
                continue

            # Call handler for data received
            try:
                self.packet_handler(data, first_connection)
                first_connection = False
            except Exception:
                LOG.error("Error in packet_handler callback",
                          exc_info=True)

        self._close_ws(ws)

    def _set_websocket_status(self, status):
        LOG.info("websocket transition to status %s", status)
        try:
            if self.status_cb:
                self.status_cb(status)
        except Exception:
            LOG.error("Error in status_cb", exc_info=True)

    def _subscribe_websocket(self):
        """ODL Websocket change notification subscription"""
        # Check ODL URL for details on this process
        # https://wiki.opendaylight.org/view/OpenDaylight_Controller:MD-SAL:Restconf:Change_event_notification_subscription#rpc_create-data-change-event-subscription # noqa: E501 # pylint: disable=line-too-long

        # Invoke rpc create-data-change-event-subscription
        ws_create_dce_subs_url = ("restconf/operations/sal-remote:"
                                  "create-data-change-event-subscription")
        odl_subscription_data = {'input': {
            'path': self.path,
            'sal-remote-augment:datastore': self.datastore,
            'sal-remote-augment:scope': self.scope,
            'sal-remote-augment:notification-output-type': 'JSON'
        }}
        try:
            response = self.odl_rest_client.sendjson('post',
                                                     ws_create_dce_subs_url,
                                                     odl_subscription_data)
            response.raise_for_status()
        except exceptions.ConnectionError:
            LOG.error("cannot connect to the opendaylight controller")
            return None
        except exceptions.HTTPError as e:
            # restconf returns 400 on operation when path is not available
            if e.response.status_code == codes.bad_request:
                LOG.debug("response code bad_request (400)"
                          "check path for websocket connection")
                raise ValueError(_("bad_request (http400),check path."))
            else:
                LOG.warning("websocket connection failed",
                            exc_info=True)
                return None
        except Exception:
            LOG.error("websocket subscription failed", exc_info=True)
            return None

        # Subscribing to stream. Returns websocket URL to listen to
        ws_dce_subs_url = """restconf/streams/stream/"""
        try:
            stream_name = response.json()
            stream_name = stream_name['output']['stream-name']
            url = ws_dce_subs_url + stream_name
            if self.leaf_node_only:
                url += "?odl-leaf-nodes-only=true"
            response = self.odl_rest_client.get(url)
            response.raise_for_status()
            stream_url = response.headers['location']
            LOG.debug("websocket stream URL: %s", stream_url)
            return stream_url
        except exceptions.ConnectionError:
            LOG.error("cannot connect to the opendaylight controller")
            return None
        except exceptions.HTTPError as e:
            # restconf returns 404 on operation when there is no entry
            if e.response.status_code == codes.not_found:
                LOG.debug("response code not_found (404)"
                          "unable to websocket connection url")
                raise ValueError(_("bad_request (http400),check path"))
            else:
                LOG.warning("websocket connection failed")
                return None
        except ValueError:
            with excutils.save_and_reraise_exception():
                LOG.error("websocket subscribe got invalid stream name")
        except KeyError:
            LOG.error("websocket subscribe got bad stream data")
            raise ValueError(_("websocket subscribe bad stream data"))
        except Exception:
            LOG.error("websocket subscription failed", exc_info=True)
            return None

    def _socket_create_connection(self, stream_url):
        ws = None
        try:
            ws = websocket.create_connection(stream_url,
                                             timeout=self.timeout)
        except ValueError:
            with excutils.save_and_reraise_exception():
                LOG.error("websocket create connection invalid URL")
        except Exception:
            # Although a number of exceptions can occur here
            # we handle them all the same way, return None.
            # As such, enough to just "except Exception."
            LOG.exception("websocket create connection failed",
                          exc_info=True)
            return None
        if ws is None or not ws.connected:
            LOG.error("websocket create connection unsuccessful")
            return None

        LOG.debug("websocket connection established")
        return ws

    def _connect_ws(self):
        self._set_websocket_status(ODL_WEBSOCKET_CONNECTING)
        stream_url = self._subscribe_websocket()
        if stream_url is None:
            return None
        if 'https:' in self.odl_rest_client.url and 'wss:' not in stream_url:
            LOG.warning('TLS ODL URL detected, but websocket URL is not.  '
                        'Forcing websocket URL to TLS')
            stream_url = stream_url.replace('ws:', 'wss:')
        # Delay here causes websocket notification lose (ODL Bug 8299)
        ws = self._socket_create_connection(stream_url)
        if ws is not None:
            self._set_websocket_status(ODL_WEBSOCKET_CONNECTED)
        return ws

    def _close_ws(self, ws):
        LOG.debug("closing websocket")
        try:
            if ws is not None:
                ws.close()
        except Exception:
            LOG.error("Error while closing websocket", exc_info=True)
        self._set_websocket_status(ODL_WEBSOCKET_DISCONNECTED)


class EventDataParser(object):
    """Helper class to parse websocket notification data"""

    NOTIFICATION_TAG = 'notification'
    DC_NOTIFICATION_TAG = 'data-changed-notification'
    DC_EVENT_TAG = 'data-change-event'
    OPERATION_DELETE = 'deleted'
    OPERATION_CREATE = 'created'
    OPERATION_UPDATE = 'updated'

    def __init__(self, item):
        self.item = item

    @classmethod
    def get_item(cls, payload):
        try:
            data = jsonutils.loads(payload)
        except ValueError:
            LOG.warning("invalid websocket notification")
            return
        try:
            dn_events = (data[cls.NOTIFICATION_TAG]
                             [cls.DC_NOTIFICATION_TAG]
                             [cls.DC_EVENT_TAG])

            if not isinstance(dn_events, list):
                dn_events = [dn_events]

            for e in dn_events:
                yield cls(e)
        except KeyError:
            LOG.warning("invalid JSON for websocket notification")

    def get_fields(self):
        return (self.get_operation(),
                self.get_path(),
                self.get_data())

    def get_path(self):
        return self.item.get('path')

    def get_data(self):
        return self.item.get('data')

    def get_operation(self):
        return self.item.get('operation')

    @staticmethod
    def extract_field(text, key):
        pattern = r'\[' + key + r'=(.*?)\]'
        match = re.search(pattern, text)
        if match:
            return match.group(1)

        return None
