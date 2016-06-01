# Copyright (c) 2013-2014 OpenStack Foundation
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

from oslo_config import cfg
from oslo_log import log as logging

from neutron.db import api as db_api
from neutron.plugins.ml2 import driver_api as api

from networking_odl.common import callback
from networking_odl.common import config as odl_conf
from networking_odl.common import constants as odl_const
from networking_odl.journal import cleanup
from networking_odl.journal import journal
from networking_odl.journal import maintenance
from networking_odl.ml2 import port_binding

LOG = logging.getLogger(__name__)


class OpenDaylightMechanismDriver(api.MechanismDriver):
    """OpenDaylight Python Driver for Neutron.

    This code is the backend implementation for the OpenDaylight ML2
    MechanismDriver for OpenStack Neutron.
    """

    def initialize(self):
        LOG.debug("Initializing OpenDaylight ML2 driver")
        cfg.CONF.register_opts(odl_conf.odl_opts, "ml2_odl")
        self.sg_handler = callback.OdlSecurityGroupsHandler(self)
        self.journal = journal.OpendaylightJournalThread()
        self.port_binding_controller = port_binding.PortBindingManager.create()
        self._start_maintenance_thread()

    def _start_maintenance_thread(self):
        # start the maintenance thread and register all the maintenance
        # operations :
        # (1) JournalCleanup - Delete completed rows from journal
        # (2) CleanupProcessing - Mark orphaned processing rows to pending
        cleanup_obj = cleanup.JournalCleanup()
        self._maintenance_thread = maintenance.MaintenanceThread()
        self._maintenance_thread.register_operation(
            cleanup_obj.delete_completed_rows)
        self._maintenance_thread.register_operation(
            cleanup_obj.cleanup_processing_rows)
        self._maintenance_thread.start()

    @staticmethod
    def _record_in_journal(context, object_type, operation, data=None):
        if data is None:
            data = context.current
        journal.record(context._plugin_context.session, object_type,
                       context.current['id'], operation, data)

    def create_network_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_NETWORK, odl_const.ODL_CREATE)

    def create_subnet_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_SUBNET, odl_const.ODL_CREATE)

    def create_port_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_PORT, odl_const.ODL_CREATE)

    def update_network_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_NETWORK, odl_const.ODL_UPDATE)

    def update_subnet_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_SUBNET, odl_const.ODL_UPDATE)

    def update_port_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_PORT, odl_const.ODL_UPDATE)

    def delete_network_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_NETWORK, odl_const.ODL_DELETE, data=[])

    def delete_subnet_precommit(self, context):
        # Use the journal row's data field to store parent object
        # uuids. This information is required for validation checking
        # when deleting parent objects.
        new_context = [context.current['network_id']]
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_SUBNET, odl_const.ODL_DELETE,
            data=new_context)

    def delete_port_precommit(self, context):
        # Use the journal row's data field to store parent object
        # uuids. This information is required for validation checking
        # when deleting parent objects.
        new_context = [context.current['network_id']]
        for subnet in context.current['fixed_ips']:
            new_context.append(subnet['subnet_id'])
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_PORT, odl_const.ODL_DELETE,
            data=new_context)

    @journal.call_thread_on_end
    def sync_from_callback(self, operation, res_type_uri, res_id,
                           resource_dict):
        object_type = res_type_uri.replace('-', '_')[:-1]
        object_uuid = (resource_dict[object_type]['id']
                       if operation == 'create' else res_id)
        if resource_dict is not None:
            resource_dict = resource_dict[object_type]
        journal.record(db_api.get_session(), object_type, object_uuid,
                       operation, resource_dict)

    def _postcommit(self, context):
        self.journal.set_sync_event()

    create_network_postcommit = _postcommit
    create_subnet_postcommit = _postcommit
    create_port_postcommit = _postcommit
    update_network_postcommit = _postcommit
    update_subnet_postcommit = _postcommit
    update_port_postcommit = _postcommit
    delete_network_postcommit = _postcommit
    delete_subnet_postcommit = _postcommit
    delete_port_postcommit = _postcommit

    def bind_port(self, port_context):
        """Set binding for a valid segments

        """
        return self.port_binding_controller.bind_port(port_context)
