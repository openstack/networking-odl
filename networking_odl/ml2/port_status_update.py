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

import threading

from neutron_lib.callbacks import resources
from neutron_lib import constants as n_const
from neutron_lib import context
from neutron_lib.plugins import directory
from neutron_lib import worker
from oslo_log import log

from neutron.db import provisioning_blocks

from networking_odl.common import client as odl_client
from networking_odl.common import odl_features
from networking_odl.common import utils
from networking_odl.common import websocket_client as odl_ws_client

LOG = log.getLogger(__name__)


class OdlPortStatusUpdate(worker.BaseWorker):
    """Class to register and handle port status update"""
    PORT_PATH = "restconf/operational/neutron:neutron/ports/port"

    def __init__(self):
        super(OdlPortStatusUpdate, self).__init__()
        self.odl_websocket_client = None

    def start(self):
        super(OdlPortStatusUpdate, self).start()
        LOG.debug('OdlPortStatusUpdate worker running')
        if odl_features.has(odl_features.OPERATIONAL_PORT_STATUS):
            self.run_websocket()

    def stop(self):
        if self.odl_websocket_client:
            self.odl_websocket_client.set_exit_flag()

    def wait(self):
        """Wait for service to complete."""

    @staticmethod
    def reset():
        pass

    def run_websocket(self):
        # OpenDaylight path to recieve websocket notifications on
        neutron_ports_path = "/neutron:neutron/neutron:ports"

        self.path_uri = utils.get_odl_url()

        self.odl_websocket_client = (
            odl_ws_client.OpenDaylightWebsocketClient.odl_create_websocket(
                self.path_uri, neutron_ports_path,
                odl_ws_client.ODL_OPERATIONAL_DATASTORE,
                odl_ws_client.ODL_NOTIFICATION_SCOPE_SUBTREE,
                self._process_websocket_recv,
                self._process_websocket_reconnect,
                True
            ))

    def _process_websocket_recv(self, payload, reconnect):
        # Callback for websocket notification
        LOG.debug("Websocket notification for port status update")
        for event in odl_ws_client.EventDataParser.get_item(payload):
            operation, path, data = event.get_fields()
            if ((operation in [event.OPERATION_UPDATE,
                 event.OPERATION_CREATE])):
                port_id = event.extract_field(path, "neutron:uuid")
                port_id = str(port_id).strip("'")
                status_field = data.get('status')
                if status_field is not None:
                    status = status_field.get('content')
                    LOG.debug("Update port for port id %s %s", port_id, status)
                    # for now we only support transition from DOWN->ACTIVE
                    # https://bugs.launchpad.net/networking-odl/+bug/1686023
                    if status == n_const.PORT_STATUS_ACTIVE:
                        provisioning_blocks.provisioning_complete(
                            context.get_admin_context(),
                            port_id, resources.PORT,
                            provisioning_blocks.L2_AGENT_ENTITY)
            if operation == event.OPERATION_DELETE:
                LOG.debug("PortStatus: Ignoring delete operation")

    def _process_websocket_reconnect(self, status):
        if status == odl_ws_client.ODL_WEBSOCKET_CONNECTED:
            # Get port data using restconf
            LOG.debug("Websocket notification on reconnection")
            reconn_thread = threading.Thread(
                name='websocket', target=self._pull_missed_statuses)
            reconn_thread.start()

    def _pull_missed_statuses(self):
        LOG.debug("starting to pull pending statuses...")
        plugin = directory.get_plugin()
        filter = {"status": [n_const.PORT_STATUS_DOWN],
                  "vif_type": ["unbound"]}
        ports = plugin.get_ports(context.get_admin_context(), filter)

        if not ports:
            LOG.debug("no down ports found, done")
            return

        port_fetch_url = utils.get_odl_url(self.PORT_PATH)
        client = odl_client.OpenDaylightRestClient.create_client(
            url=port_fetch_url)

        for port in ports:
            id = port["id"]
            response = client.get(id)
            if response.status_code != 200:
                LOG.warning("Non-200 response code %s", str(response))
                continue
            odl_status = response.json()['port'][0]['status']
            if odl_status == n_const.PORT_STATUS_ACTIVE:
                # for now we only support transition from DOWN->ACTIVE
                # See https://bugs.launchpad.net/networking-odl/+bug/1686023
                provisioning_blocks.provisioning_complete(
                    context.get_admin_context(),
                    id, resources.PORT,
                    provisioning_blocks.L2_AGENT_ENTITY)
        LOG.debug("done pulling pending statuses")
