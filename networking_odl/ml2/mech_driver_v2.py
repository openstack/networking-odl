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

from neutron.extensions import portbindings
from neutron.plugins.ml2 import driver_api as api

from networking_odl.common import config as odl_conf
from networking_odl.common import journal
from networking_odl.db import db
from networking_odl.ml2 import network_topology

LOG = logging.getLogger(__name__)


class OpenDaylightMechanismDriver(api.MechanismDriver):
    """OpenDaylight Python Driver for Neutron.

    This code is the backend implementation for the OpenDaylight ML2
    MechanismDriver for OpenStack Neutron.
    """

    def initialize(self):
        LOG.debug("Initializing OpenDaylight ML2 driver")
        cfg.CONF.register_opts(odl_conf.odl_opts, "ml2_odl")
        self.vif_details = {portbindings.CAP_PORT_FILTER: True}
        self.journal = journal.OpendaylightJournalThread()
        self._network_topology = network_topology.NetworkTopologyManager()

    @journal.call_thread_on_end
    def create_network_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'network',
                              context.current['id'], 'create', context.current)

    @journal.call_thread_on_end
    def create_subnet_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'subnet',
                              context.current['id'], 'create', context.current)

    @journal.call_thread_on_end
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

    @journal.call_thread_on_end
    def update_network_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'network',
                              context.current['id'], 'update', context.current)

    @journal.call_thread_on_end
    def update_subnet_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'subnet',
                              context.current['id'], 'update', context.current)

    @journal.call_thread_on_end
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

    @journal.call_thread_on_end
    def delete_network_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'network',
                              context.current['id'], 'delete', context.current)

    @journal.call_thread_on_end
    def delete_subnet_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'subnet',
                              context.current['id'], 'delete', context.current)

    @journal.call_thread_on_end
    def delete_port_precommit(self, context):
        db.create_pending_row(context._plugin_context.session, 'port',
                              context.current['id'], 'delete', context.current)

    def bind_port(self, port_context):
        """Set binding for a valid segments

        """
        return self._network_topology.bind_port(port_context)
