# Copyright (c) 2017 Ericsson India Global Service Pvt Ltd.
# All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#

from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib import constants as n_const
from neutron_lib import context
from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from neutron.services.trunk import constants as t_consts
from neutron.services.trunk.drivers import base as trunk_base

from networking_odl.common import config as odl_conf
from networking_odl.common import constants as odl_const
from networking_odl.journal import full_sync
from networking_odl.journal import journal
from networking_odl.trunk import constants as odltrunk_const

LOG = logging.getLogger(__name__)

TRUNK_RESOURCES = {
    odl_const.ODL_TRUNK: odl_const.ODL_TRUNKS
}


@registry.has_registry_receivers
class OpenDaylightTrunkHandlerV2(object):
    def __init__(self):
        cfg.CONF.register_opts(odl_conf.odl_opts, "ml2_odl")
        self.journal = journal.OpenDaylightJournalThread()
        full_sync.register(t_consts.TRUNK, TRUNK_RESOURCES)
        LOG.info('initialized trunk driver for OpendayLight')

    @staticmethod
    def _record_in_journal(context, trunk_id, operation, data):
        journal.record(context, odl_const.ODL_TRUNK, trunk_id, operation, data)

    # TODO(vthapar) Revisit status updates once websockets are fully
    # implemented - https://review.openstack.org/#/c/421127/
    @log_helpers.log_method_call
    def trunk_create_precommit(self, resource, event, trunk_plugin, payload):
        data = payload.current_trunk.to_dict()
        data['status'] = t_consts.ACTIVE_STATUS
        self._record_in_journal(payload.context, payload.trunk_id,
                                odl_const.ODL_CREATE, data)

    @log_helpers.log_method_call
    def trunk_update_precommit(self, resource, event,
                               trunk_plugin, payload=None):
        if isinstance(payload, events.EventPayload):
            # TODO(boden): remove shim once all callbacks use lib paylaods
            payload.desired_state.update(status=t_consts.ACTIVE_STATUS)
            data = payload.desired_state.to_dict()
            trunk_id = payload.resource_id
        else:
            payload.current_trunk.update(status=t_consts.ACTIVE_STATUS)
            data = payload.current_trunk.to_dict()
            trunk_id = payload.trunk_id

        self._record_in_journal(payload.context, trunk_id,
                                odl_const.ODL_UPDATE, data)

    @log_helpers.log_method_call
    def trunk_delete_precommit(self, resource, event, trunk_plugin, payload):
        # fill in data with parent ids, will be used in parent validations
        trunk_dict = payload.original_trunk.to_dict()
        data = [subport['port_id'] for subport in trunk_dict['sub_ports']]
        data.append(trunk_dict['port_id'])
        self._record_in_journal(payload.context, payload.trunk_id,
                                odl_const.ODL_DELETE, data)

    @log_helpers.log_method_call
    def trunk_create_postcommit(self, resource, event, trunk_plugin, payload):
        payload.current_trunk.update(status=t_consts.ACTIVE_STATUS)
        self.journal.set_sync_event()

    @log_helpers.log_method_call
    def trunk_update_postcommit(self, resource, event, trunk_plugin, payload):
        payload.current_trunk.update(status=t_consts.ACTIVE_STATUS)
        self.journal.set_sync_event()

    @log_helpers.log_method_call
    def trunk_delete_postcommit(self, resource, event, trunk_plugin, payload):
        self.journal.set_sync_event()

    @log_helpers.log_method_call
    def trunk_subports_set_status(self, resource, event, trunk_plugin,
                                  payload):
        core_plugin = directory.get_plugin()
        admin_context = context.get_admin_context()

        if event == events.AFTER_DELETE:
            status = n_const.PORT_STATUS_DOWN
        else:
            parent_id = payload.current_trunk.port_id
            parent_port = core_plugin._get_port(admin_context, parent_id)
            status = parent_port['status']

        for subport in payload.subports:
            self._set_subport_status(core_plugin, admin_context,
                                     subport.port_id, status)

    @log_helpers.log_method_call
    def trunk_subports_update_status(self, resource, event, trigger, **kwargs):
        core_plugin = directory.get_plugin()
        admin_context = context.get_admin_context()
        port = kwargs['port']
        original_port = kwargs['original_port']
        if port['status'] == original_port['status']:
            return
        for subport_id in self._get_subports_ids(port['id']):
            self._set_subport_status(core_plugin, admin_context, subport_id,
                                     port['status'])

    def _set_subport_status(self, plugin, admin_context, port_id, status):
        plugin.update_port_status(admin_context, port_id, status)

    def _get_subports_ids(self, port_id):
        trunk_plugin = directory.get_plugin('trunk')
        filters = {'port_id': port_id}
        trunks = trunk_plugin.get_trunks(context.get_admin_context(),
                                         filters=filters)
        if not trunks:
            return ()
        trunk = trunks[0]
        return (subport['port_id'] for subport in trunk['sub_ports'])


@registry.has_registry_receivers
class OpenDaylightTrunkDriverV2(trunk_base.DriverBase):
    @property
    def is_loaded(self):
        try:
            return (odl_const.ODL_ML2_MECH_DRIVER_V2 in
                    cfg.CONF.ml2.mechanism_drivers)
        except cfg.NoSuchOptError:
            return False

    @registry.receives(t_consts.TRUNK_PLUGIN, [events.AFTER_INIT])
    def register(self, resource, event, trigger, payload=None):
        super(OpenDaylightTrunkDriverV2, self).register(
            resource, event, trigger, payload=payload)
        self._handler = OpenDaylightTrunkHandlerV2()
        registry.subscribe(self._handler.trunk_create_precommit,
                           t_consts.TRUNK, events.PRECOMMIT_CREATE)
        registry.subscribe(self._handler.trunk_create_postcommit,
                           t_consts.TRUNK, events.AFTER_CREATE)
        registry.subscribe(self._handler.trunk_update_precommit,
                           t_consts.TRUNK, events.PRECOMMIT_UPDATE)
        registry.subscribe(self._handler.trunk_update_postcommit,
                           t_consts.TRUNK, events.AFTER_UPDATE)
        registry.subscribe(self._handler.trunk_delete_precommit,
                           t_consts.TRUNK, events.PRECOMMIT_DELETE)
        registry.subscribe(self._handler.trunk_delete_postcommit,
                           t_consts.TRUNK, events.AFTER_DELETE)
        for event_ in (events.PRECOMMIT_CREATE, events.PRECOMMIT_DELETE):
            registry.subscribe(self._handler.trunk_update_precommit,
                               t_consts.SUBPORTS, event_)
        for event_ in (events.AFTER_CREATE, events.AFTER_DELETE):
            registry.subscribe(self._handler.trunk_update_postcommit,
                               t_consts.SUBPORTS, event_)
            # Upon subport creation/deletion we need to set the right port
            # status:
            # 1. Set it to parent status when it is attached to the trunk
            # 2. Set it to down when is removed from the trunk
            registry.subscribe(self._handler.trunk_subports_set_status,
                               t_consts.SUBPORTS, event_)
        # NOTE(ltomasbo): if the status of the parent port changes, the
        # subports need to update their status too
        registry.subscribe(self._handler.trunk_subports_update_status,
                           resources.PORT, events.AFTER_UPDATE)

    @classmethod
    def create(cls):
        return cls(odl_const.ODL_ML2_MECH_DRIVER_V2,
                   odltrunk_const.SUPPORTED_INTERFACES,
                   odltrunk_const.SUPPORTED_SEGMENTATION_TYPES,
                   None,
                   can_trunk_bound_port=True)
