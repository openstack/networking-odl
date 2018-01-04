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

from debtcollector import removals

from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils

from neutron.services.trunk import constants as t_consts
from neutron.services.trunk.drivers import base as trunk_base

from networking_odl.common import client as odl_client
from networking_odl.common import constants as odl_const
from networking_odl.trunk import constants as odltrunk_const


LOG = logging.getLogger(__name__)

# NOTE: Status handling
# V1 driver assumes if status=ACTIVE by default and sets it before making
# Create/Update rest calls to ODL.
# In case of failure in rest, it resets it to DEGRADED.


@registry.has_registry_receivers
@removals.removed_class(
    'OpenDaylightTrunkHandlerV1', version='Queens', removal_version='Rocky',
    message="Usage of V1 drivers is deprecated. Please use V2 instead.")
class OpenDaylightTrunkHandlerV1(object):
    def __init__(self):
        self.client = odl_client.OpenDaylightRestClient.create_client()
        LOG.info('initialized trunk driver for OpendayLight')

    def trunk_create_postcommit(self, trunk):
        trunk.update(status=t_consts.ACTIVE_STATUS)
        trunk_dict = trunk.to_dict()
        try:
            self.client.sendjson('post', odl_const.ODL_TRUNKS,
                                 {odl_const.ODL_TRUNK: trunk_dict})
        except Exception:
            with excutils.save_and_reraise_exception():
                trunk.update(status=t_consts.DEGRADED_STATUS)

    def trunk_delete_postcommit(self, trunk):
        trunk_dict = trunk.to_dict()
        url = odl_const.ODL_TRUNKS + '/' + trunk_dict['id']
        self.client.try_delete(url)

    def trunk_update_postcommit(self, updated):
        updated.update(status=t_consts.ACTIVE_STATUS)
        trunk_dict = updated.to_dict()
        try:
            url = odl_const.ODL_TRUNKS + '/' + trunk_dict['id']
            self.client.sendjson('put', url,
                                 {odl_const.ODL_TRUNK: trunk_dict})
        except Exception:
            with excutils.save_and_reraise_exception():
                updated.update(status=t_consts.DEGRADED_STATUS)

    @registry.receives(t_consts.TRUNK, (events.AFTER_CREATE,
                                        events.AFTER_DELETE,
                                        events.AFTER_UPDATE))
    def trunk_event(self, resource, event, trunk_plugin, payload):
        if event == events.AFTER_CREATE:
            self.trunk_create_postcommit(payload.current_trunk)
        if event == events.AFTER_UPDATE:
            self.trunk_update_postcommit(payload.current_trunk)
        elif event == events.AFTER_DELETE:
            self.trunk_delete_postcommit(payload.original_trunk)

    @registry.receives(t_consts.SUBPORTS, (events.AFTER_CREATE,
                                           events.AFTER_DELETE))
    def subport_event(self, resource, event, trunk_plugin, payload):
        self.trunk_update_postcommit(payload.current_trunk)


class OpenDaylightTrunkDriverV1(trunk_base.DriverBase):
    @property
    def is_loaded(self):
        try:
            return (odl_const.ODL_ML2_MECH_DRIVER_V1 in
                    cfg.CONF.ml2.mechanism_drivers)
        except cfg.NoSuchOptError:
            return False

    @registry.receives(t_consts.TRUNK_PLUGIN, [events.AFTER_INIT])
    def register(self, resource, event, trigger, payload=None):
        super(OpenDaylightTrunkDriverV1, self).register(
            resource, event, trigger, payload=payload)
        self._handler = OpenDaylightTrunkHandlerV1()

    @classmethod
    def create(cls):
        return cls(odl_const.ODL_ML2_MECH_DRIVER_V1,
                   odltrunk_const.SUPPORTED_INTERFACES,
                   odltrunk_const.SUPPORTED_SEGMENTATION_TYPES,
                   None,
                   can_trunk_bound_port=True)
