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
import copy

from oslo_config import cfg
from oslo_log import log as logging

from neutron.db import api as db_api
from neutron.plugins.ml2 import driver_api as api

from networking_odl.common import callback
from networking_odl.common import config as odl_conf
from networking_odl.db import db
from networking_odl.journal import journal
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

    def create_network_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'network',
                              context.current['id'], 'create', context.current)

    def create_subnet_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'subnet',
                              context.current['id'], 'create', context.current)

    def create_port_precommit(self, context):
        dbcontext = context._plugin_context
        groups = [context._plugin.get_security_group(dbcontext, sg)
                  for sg in context.current['security_groups']]
        new_context = copy.deepcopy(context.current)
        new_context['security_groups'] = groups
        # NOTE(yamahata): work around for port creation for router
        # tenant_id=''(empty string) is passed when port is created
        # by l3 plugin internally for router.
        # On the other hand, ODL doesn't accept empty string for tenant_id.
        # In that case, deduce tenant_id from network_id for now.
        # Right fix: modify Neutron so that don't allow empty string
        # for tenant_id even for port for internal use.
        # TODO(yamahata): eliminate this work around when neutron side
        # is fixed
        # assert port['tenant_id'] != ''
        if ('tenant_id' not in context.current or
                context.current['tenant_id'] == ''):
            tenant_id = context._network_context._network['tenant_id']
            new_context['tenant_id'] = tenant_id
        db.create_pending_row(context._plugin_context.session, 'port',
                              context.current['id'], 'create', new_context)

    def update_network_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'network',
                              context.current['id'], 'update', context.current)

    def update_subnet_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'subnet',
                              context.current['id'], 'update', context.current)

    def update_port_precommit(self, context):
        port = context._plugin.get_port(context._plugin_context,
                                        context.current['id'])
        dbcontext = context._plugin_context
        new_context = copy.deepcopy(context.current)
        groups = [context._plugin.get_security_group(dbcontext, sg)
                  for sg in port['security_groups']]
        new_context['security_groups'] = groups
        # Add the network_id in for validation
        new_context['network_id'] = port['network_id']
        # NOTE(yamahata): work around for port creation for router
        # tenant_id=''(empty string) is passed when port is created
        # by l3 plugin internally for router.
        # On the other hand, ODL doesn't accept empty string for tenant_id.
        # In that case, deduce tenant_id from network_id for now.
        # Right fix: modify Neutron so that don't allow empty string
        # for tenant_id even for port for internal use.
        # TODO(yamahata): eliminate this work around when neutron side
        # is fixed
        # assert port['tenant_id'] != ''
        if ('tenant_id' not in context.current or
                context.current['tenant_id'] == ''):
            port['tenant_id'] = context._network_context._network['tenant_id']
        db.create_pending_row(context._plugin_context.session, 'port',
                              context.current['id'], 'update', new_context)

    def delete_network_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'network',
                              context.current['id'], 'delete', None)

    def delete_subnet_precommit(self, context):
        # Use the journal row's data field to store parent object
        # uuids. This information is required for validation checking
        # when deleting parent objects.
        new_context = [context.current['network_id']]
        db.create_pending_row(context._plugin_context.session, 'subnet',
                              context.current['id'], 'delete', new_context)

    def delete_port_precommit(self, context):
        # Use the journal row's data field to store parent object
        # uuids. This information is required for validation checking
        # when deleting parent objects.
        new_context = [context.current['network_id']]
        for subnet in context.current['fixed_ips']:
            new_context.append(subnet['subnet_id'])
        db.create_pending_row(context._plugin_context.session, 'port',
                              context.current['id'], 'delete', new_context)

    @journal.call_thread_on_end
    def sync_from_callback(self, operation, res_type_uri, res_id,
                           resource_dict):
        object_type = res_type_uri.replace('-', '_')[:-1]
        object_uuid = (resource_dict[object_type]['id']
                       if operation == 'create' else res_id)
        if resource_dict is not None:
            resource_dict = resource_dict[object_type]
        db.create_pending_row(db_api.get_session(), object_type, object_uuid,
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
