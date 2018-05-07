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

from neutron_lib.api.definitions import multiprovidernet as mpnet_apidef
from neutron_lib.api.definitions import provider_net as providernet
from neutron_lib import constants as p_const
from neutron_lib.plugins import constants as nlib_const
from neutron_lib.plugins.ml2 import api
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from networking_odl.common import callback
from networking_odl.common import config as odl_conf
from networking_odl.common import constants as odl_const
from networking_odl.common import odl_features
from networking_odl.common import postcommit
from networking_odl.dhcp import odl_dhcp_driver as dhcp_driver
from networking_odl.journal import base_driver
from networking_odl.journal import full_sync
from networking_odl.journal import journal
from networking_odl.journal import worker
from networking_odl.ml2 import port_binding
from networking_odl.ml2 import port_status_update
from networking_odl.qos import qos_driver_v2 as qos_driver
from networking_odl.trunk import trunk_driver_v2 as trunk_driver

LOG = logging.getLogger(__name__)


@postcommit.add_postcommit('network', 'subnet', 'port')
class OpenDaylightMechanismDriver(api.MechanismDriver,
                                  base_driver.ResourceBaseDriver):
    """OpenDaylight Python Driver for Neutron.

    This code is the backend implementation for the OpenDaylight ML2
    MechanismDriver for OpenStack Neutron.
    """
    RESOURCES = {
        odl_const.ODL_SG: odl_const.ODL_SGS,
        odl_const.ODL_SG_RULE: odl_const.ODL_SG_RULES,
        odl_const.ODL_NETWORK: odl_const.ODL_NETWORKS,
        odl_const.ODL_SUBNET: odl_const.ODL_SUBNETS,
        odl_const.ODL_PORT: odl_const.ODL_PORTS
    }
    plugin_type = nlib_const.CORE

    def initialize(self):
        LOG.debug("Initializing OpenDaylight ML2 driver")
        cfg.CONF.register_opts(odl_conf.odl_opts, "ml2_odl")
        self.sg_handler = callback.OdlSecurityGroupsHandler(
            self.sync_from_callback_precommit,
            self.sync_from_callback_postcommit)
        self.journal = journal.OpenDaylightJournalThread()
        self.port_binding_controller = port_binding.PortBindingManager.create()
        self.trunk_driver = trunk_driver.OpenDaylightTrunkDriverV2.create()
        if cfg.CONF.ml2_odl.enable_dhcp_service:
            self.dhcp_driver = dhcp_driver.OdlDhcpDriver()

        full_sync.register(nlib_const.CORE, self.RESOURCES)
        odl_features.init()

        if odl_const.ODL_QOS in cfg.CONF.ml2.extension_drivers:
            qos_driver.OpenDaylightQosDriver.create()

    def get_workers(self):
        workers = [port_status_update.OdlPortStatusUpdate(),
                   worker.JournalPeriodicProcessor()]
        workers += self.port_binding_controller.get_workers()
        return workers

    @staticmethod
    def _record_in_journal(context, object_type, operation, data=None):
        if data is None:
            data = context.current
        journal.record(context._plugin_context, object_type,
                       context.current['id'], operation, data,
                       ml2_context=context)

    @log_helpers.log_method_call
    def create_network_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_NETWORK, odl_const.ODL_CREATE)

    @log_helpers.log_method_call
    def create_subnet_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_SUBNET, odl_const.ODL_CREATE)

    @log_helpers.log_method_call
    def create_port_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_PORT, odl_const.ODL_CREATE)

    @log_helpers.log_method_call
    def update_network_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_NETWORK, odl_const.ODL_UPDATE)

    @log_helpers.log_method_call
    def update_subnet_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_SUBNET, odl_const.ODL_UPDATE)

    @log_helpers.log_method_call
    def update_port_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_PORT, odl_const.ODL_UPDATE)

    @log_helpers.log_method_call
    def delete_network_precommit(self, context):
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_NETWORK, odl_const.ODL_DELETE, data=[])

    @log_helpers.log_method_call
    def delete_subnet_precommit(self, context):
        # Use the journal row's data field to store parent object
        # uuids. This information is required for validation checking
        # when deleting parent objects.
        new_context = [context.current['network_id']]
        OpenDaylightMechanismDriver._record_in_journal(
            context, odl_const.ODL_SUBNET, odl_const.ODL_DELETE,
            data=new_context)

    @log_helpers.log_method_call
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

    def _sync_security_group_create_precommit(
            self, context, operation, object_type, res_id, sg_dict):

        journal.record(context, object_type, sg_dict['id'], operation, sg_dict)

        # NOTE(yamahata): when security group is created, default rules
        # are also created.
        for rule in sg_dict['security_group_rules']:
            journal.record(context, odl_const.ODL_SG_RULE, rule['id'],
                           odl_const.ODL_CREATE, rule)

    @log_helpers.log_method_call
    def sync_from_callback_precommit(self, context, operation, res_type,
                                     res_id, resource_dict, **kwargs):
        object_type = res_type.singular
        if resource_dict is not None:
            resource_dict = resource_dict[object_type]

        if (operation == odl_const.ODL_CREATE and
                object_type == odl_const.ODL_SG):
            self._sync_security_group_create_precommit(
                context, operation, object_type, res_id, resource_dict)
            return

        object_uuid = (resource_dict.get('id')
                       if operation == 'create' else res_id)
        data = resource_dict

        if (operation == odl_const.ODL_DELETE):
            # NOTE(yamahata): DB auto deletion
            # Security Group Rule under this Security Group needs to
            # be deleted. At NeutronDB layer rules are auto deleted with
            # cascade='all,delete'.
            if (object_type == odl_const.ODL_SG):
                for rule_id in kwargs['security_group_rule_ids']:
                    journal.record(context, odl_const.ODL_SG_RULE,
                                   rule_id, odl_const.ODL_DELETE,
                                   [object_uuid])
            elif (object_type == odl_const.ODL_SG_RULE):
                # Set the parent security group id so that dependencies
                # to this security rule deletion can be properly found
                # in the journal.
                data = [kwargs['security_group_id']]

        assert object_uuid is not None
        journal.record(context, object_type, object_uuid,
                       operation, data)

    def sync_from_callback_postcommit(self, context, operation, res_type,
                                      res_id, resource_dict, **kwargs):
        self._postcommit(context)

    def _postcommit(self, context):
        self.journal.set_sync_event()

    @log_helpers.log_method_call
    def bind_port(self, port_context):
        """Set binding for a valid segments

        """
        return self.port_binding_controller.bind_port(port_context)

    def check_vlan_transparency(self, context):
        """Check VLAN transparency

        """
        # TODO(yamahata): This should be odl service provider dependent
        # introduce ODL yang model for ODL to report which network types
        # are vlan-transparent.
        # VLAN and FLAT cases, we don't know if the underlying network
        # supports QinQ or VLAN.
        # For now, netvirt supports only vxlan tunneling.
        VLAN_TRANSPARENT_NETWORK_TYPES = [p_const.TYPE_VXLAN]
        network = context.current
        # see TypeManager._extend_network_dict_provider()
        # single providernet
        if providernet.NETWORK_TYPE in network:
            return (network[providernet.NETWORK_TYPE] in
                    VLAN_TRANSPARENT_NETWORK_TYPES)
        # multi providernet
        segments = network.get(mpnet_apidef.SEGMENTS)
        if segments is None:
            return True
        return all(segment[providernet.NETWORK_TYPE]
                   in VLAN_TRANSPARENT_NETWORK_TYPES
                   for segment in segments)
