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

from oslo_config import cfg
from oslo_log import log as logging

from neutron.callbacks import events
from neutron.callbacks import registry
from neutron.services.trunk import constants as t_consts
from neutron.services.trunk.drivers import base as trunk_base

from networking_odl._i18n import _LI
from networking_odl.common import config as odl_conf
from networking_odl.common import constants as odl_const
from networking_odl.journal import journal
from networking_odl.trunk import constants as odltrunk_const

LOG = logging.getLogger(__name__)


class OpenDaylightTrunkHandlerV2(object):
    def __init__(self):
        cfg.CONF.register_opts(odl_conf.odl_opts, "ml2_odl")
        self.journal = journal.OpendaylightJournalThread()
        LOG.info(_LI('initialized trunk driver for OpendayLight'))

    @staticmethod
    def _record_in_journal(context, trunk_id, operation, data):
        journal.record(context, context, odl_const.ODL_TRUNK,
                       trunk_id, operation, data)

    # TODO(vthapar) Revisit status updates once websockets are fully
    # implemented - https://review.openstack.org/#/c/421127/
    def trunk_create_precommit(self, resource, event, trunk_plugin, payload):
        data = payload.current_trunk.to_dict()
        data['status'] = t_consts.ACTIVE_STATUS
        self._record_in_journal(payload.context, payload.trunk_id,
                                odl_const.ODL_CREATE, data)

    def trunk_update_precommit(self, resource, event, trunk_plugin, payload):
        payload.current_trunk.update(status=t_consts.ACTIVE_STATUS)
        data = payload.current_trunk.to_dict()
        self._record_in_journal(payload.context, payload.trunk_id,
                                odl_const.ODL_UPDATE, data)

    def trunk_delete_precommit(self, resource, event, trunk_plugin, payload):
        # fill in data with parent ids, will be used in parent validations
        trunk_dict = payload.original_trunk.to_dict()
        data = [subport['port_id'] for subport in trunk_dict['sub_ports']]
        data.append(trunk_dict['port_id'])
        self._record_in_journal(payload.context, payload.trunk_id,
                                odl_const.ODL_DELETE, data)

    def trunk_create_postcommit(self, resource, event, trunk_plugin, payload):
        payload.current_trunk.update(status=t_consts.ACTIVE_STATUS)
        self.journal.set_sync_event()

    def trunk_update_postcommit(self, resource, event, trunk_plugin, payload):
        payload.current_trunk.update(status=t_consts.ACTIVE_STATUS)
        self.journal.set_sync_event()

    def trunk_delete_postcommit(self, resource, event, trunk_plugin, payload):
        self.journal.set_sync_event()


class OpenDaylightTrunkDriverV2(trunk_base.DriverBase):
    @property
    def is_loaded(self):
        try:
            return (odl_const.ODL_ML2_MECH_DRIVER_V2 in
                    cfg.CONF.ml2.mechanism_drivers)
        except cfg.NoSuchOptError:
            return False

    def register(self, resource, event, trigger, **kwargs):
        super(OpenDaylightTrunkDriverV2, self).register(
            resource, event, trigger, **kwargs)
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
        for event in (events.PRECOMMIT_CREATE, events.PRECOMMIT_DELETE):
            registry.subscribe(self._handler.trunk_update_precommit,
                               t_consts.SUBPORTS, event)
        for event in (events.AFTER_CREATE, events.AFTER_DELETE):
            registry.subscribe(self._handler.trunk_update_postcommit,
                               t_consts.SUBPORTS, event)

    @classmethod
    def create(cls):
        return cls(odl_const.ODL_ML2_MECH_DRIVER_V2,
                   odltrunk_const.SUPPORTED_INTERFACES,
                   odltrunk_const.SUPPORTED_SEGMENTATION_TYPES,
                   None,
                   can_trunk_bound_port=True)
