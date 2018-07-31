# Copyright 2018 Intel Corporation.
# Copyright 2018 Isaku Yamahata <isaku.yamahata at intel com>
#                               <isaku.yamahata at gmail com>
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

from neutron.objects import router as l3_obj
from neutron.services.l3_router.service_providers import base
from neutron_lib.callbacks import events
from neutron_lib.callbacks import priority_group
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib import constants as q_const
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from networking_odl.common import constants as odl_const
from networking_odl.journal import full_sync
from networking_odl.journal import journal


LOG = logging.getLogger(__name__)

L3_RESOURCES = {
    odl_const.ODL_ROUTER: odl_const.ODL_ROUTERS,
    odl_const.ODL_FLOATINGIP: odl_const.ODL_FLOATINGIPS
}


@registry.has_registry_receivers
class ODLL3ServiceProvider(base.L3ServiceProvider):
    @log_helpers.log_method_call
    def __init__(self, l3_plugin):
        super(ODLL3ServiceProvider, self).__init__(l3_plugin)
        self.journal = journal.OpenDaylightJournalThread()
        # TODO(yamahata): add method for fullsync to retrieve
        # all the router with odl service provider.
        # other router with other service provider should be filtered.
        full_sync.register(plugin_constants.L3, L3_RESOURCES)
        self.odl_provider = __name__ + "." + self.__class__.__name__

    @property
    def _flavor_plugin(self):
        try:
            return self._flavor_plugin_ref
        except AttributeError:
            self._flavor_plugin_ref = directory.get_plugin(
                plugin_constants.FLAVORS)
            return self._flavor_plugin_ref

    def _validate_l3_flavor(self, context, router_id):
        if router_id is None:
            return False
        router = l3_obj.Router.get_object(context, id=router_id)
        flavor = self._flavor_plugin.get_flavor(context, router.flavor_id)
        provider = self._flavor_plugin.get_flavor_next_provider(
            context, flavor['id'])[0]
        return str(provider['driver']) == self.odl_provider

    def _update_floatingip_status(self, context, fip_dict):
        port_id = fip_dict.get('port_id')
        status = q_const.ACTIVE if port_id else q_const.DOWN
        l3_obj.FloatingIP.update_object(context, {'status': status},
                                        id=fip_dict['id'])

    @registry.receives(resources.ROUTER_CONTROLLER,
                       [events.PRECOMMIT_ADD_ASSOCIATION])
    @log_helpers.log_method_call
    def _router_add_association(self, resource, event, trigger, **kwargs):
        context = kwargs['context']
        router_dict = kwargs['router']
        router_dict['gw_port_id'] = kwargs['router_db'].gw_port_id
        router_id = kwargs['router_id']
        if not self._validate_l3_flavor(context, router_id):
            return
        journal.record(context, odl_const.ODL_ROUTER, router_dict['id'],
                       odl_const.ODL_CREATE, router_dict)

    @registry.receives(resources.ROUTER, [events.PRECOMMIT_UPDATE],
                       priority_group.PRIORITY_ROUTER_DRIVER)
    @log_helpers.log_method_call
    def _router_update_precommit(self, resource, event, trigger, **kwargs):
        # NOTE(manjeets) router update bypasses the driver controller
        # and argument type is different.
        payload = kwargs.get('payload', None)
        if payload:
            context = payload.context
            router_id = payload.states[0]['id']
            router_dict = payload.request_body
            gw_port_id = payload.states[0]['gw_port_id']
        else:
            # TODO(manjeets) Remove this shim once payload is fully adapted
            # https://bugs.launchpad.net/neutron/+bug/1747747
            context = kwargs['context']
            router_id = kwargs['router_db'].id
            router_dict = kwargs['router']
            gw_port_id = kwargs['router_db'].gw_port_id
        if not self._validate_l3_flavor(context, router_id):
            return
        if 'gw_port_id' not in router_dict:
                router_dict['gw_port_id'] = gw_port_id
        journal.record(context, odl_const.ODL_ROUTER,
                       router_id, odl_const.ODL_UPDATE, router_dict)

    @registry.receives(resources.ROUTER_CONTROLLER,
                       [events.PRECOMMIT_DELETE_ASSOCIATIONS])
    @log_helpers.log_method_call
    def _router_del_association(self, resource, event, trigger, **kwargs):
        router_id = kwargs['router_db'].id
        context = kwargs['context']
        if not self._validate_l3_flavor(context, router_id):
            return
        # TODO(yamahata): process floating ip etc. or just raise error?
        dependency_list = [kwargs['router_db'].gw_port_id]
        journal.record(context, odl_const.ODL_ROUTER, router_id,
                       odl_const.ODL_DELETE, dependency_list)

    @registry.receives(resources.FLOATING_IP, [events.PRECOMMIT_CREATE])
    @log_helpers.log_method_call
    def _floatingip_create_precommit(self, resource, event, trigger, **kwargs):
        context = kwargs['context']
        fip_dict = copy.deepcopy(kwargs['floatingip'])
        router_id = kwargs['floatingip_db'].router_id
        if not self._validate_l3_flavor(context, router_id):
            return
        fip_dict['id'] = kwargs['floatingip_id']
        self._update_floatingip_status(context, fip_dict)
        if fip_dict['floating_ip_address'] is None:
            fip_dict['floating_ip_address'] = \
                kwargs['floatingip_db'].floating_ip_address
        journal.record(context, odl_const.ODL_FLOATINGIP, fip_dict['id'],
                       odl_const.ODL_CREATE, fip_dict)

    @registry.receives(resources.FLOATING_IP, [events.PRECOMMIT_UPDATE])
    @log_helpers.log_method_call
    def _floatingip_update_precommit(self, resource, event, trigger, **kwargs):
        context = kwargs['context']
        fip_dict = kwargs['floatingip']
        router_id = kwargs['floatingip_db'].router_id
        fip_dict['id'] = kwargs['floatingip_db'].id
        if not self._validate_l3_flavor(context, router_id):
            return
        self._update_floatingip_status(context, fip_dict)
        journal.record(context, odl_const.ODL_FLOATINGIP, fip_dict['id'],
                       odl_const.ODL_UPDATE, fip_dict)

    @registry.receives(resources.FLOATING_IP, [events.PRECOMMIT_DELETE])
    @log_helpers.log_method_call
    def _floatingip_delete_precommit(self, resource, event, trigger, **kwargs):
        context = kwargs['context']
        fip_data = l3_obj.FloatingIP.get_objects(
            context,
            floating_port_id=kwargs['port']['id'])[0]
        if not self._validate_l3_flavor(context, fip_data.router_id):
            return
        dependency_list = [fip_data.router_id, fip_data.floating_network_id]
        journal.record(context, odl_const.ODL_FLOATINGIP, fip_data.id,
                       odl_const.ODL_DELETE, dependency_list)

    @registry.receives(resources.FLOATING_IP, [events.AFTER_CREATE,
                                               events.AFTER_UPDATE,
                                               events.AFTER_DELETE])
    @registry.receives(resources.ROUTER, [events.AFTER_CREATE,
                                          events.AFTER_UPDATE,
                                          events.AFTER_DELETE])
    @log_helpers.log_method_call
    def _l3_postcommit(self, resource, event, trigger, **kwargs):
        self.journal.set_sync_event()
