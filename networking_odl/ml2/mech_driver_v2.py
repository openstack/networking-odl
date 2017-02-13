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

from neutron.db.models import securitygroup
from neutron.extensions import multiprovidernet as mpnet
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import driver_api as api
from neutron_lib.api.definitions import provider_net as providernet
from neutron_lib.plugins import directory

from networking_odl._i18n import _, _LE
from networking_odl.common import callback
from networking_odl.common import config as odl_conf
from networking_odl.common import constants as odl_const
from networking_odl.journal import cleanup
from networking_odl.journal import full_sync
from networking_odl.journal import journal
from networking_odl.journal import maintenance
from networking_odl.journal import recovery
from networking_odl.ml2 import port_binding
from networking_odl.trunk import trunk_driver_v2 as trunk_driver

LOG = logging.getLogger(__name__)


class OpenDaylightMechanismDriver(api.MechanismDriver):
    """OpenDaylight Python Driver for Neutron.

    This code is the backend implementation for the OpenDaylight ML2
    MechanismDriver for OpenStack Neutron.
    """

    def initialize(self):
        LOG.debug("Initializing OpenDaylight ML2 driver")
        cfg.CONF.register_opts(odl_conf.odl_opts, "ml2_odl")
        self.sg_handler = callback.OdlSecurityGroupsHandler(
            self.sync_from_callback_precommit,
            self.sync_from_callback_postcommit)
        self.journal = journal.OpendaylightJournalThread()
        self.port_binding_controller = port_binding.PortBindingManager.create()
        self.trunk_driver = trunk_driver.OpenDaylightTrunkDriverV2.create()
        self._start_maintenance_thread()

    def _start_maintenance_thread(self):
        # start the maintenance thread and register all the maintenance
        # operations :
        # (1) JournalCleanup - Delete completed rows from journal
        # (2) CleanupProcessing - Mark orphaned processing rows to pending
        # (3) Full sync - Re-sync when detecting an ODL "cold reboot"
        cleanup_obj = cleanup.JournalCleanup()
        self._maintenance_thread = maintenance.MaintenanceThread()
        self._maintenance_thread.register_operation(
            cleanup_obj.delete_completed_rows)
        self._maintenance_thread.register_operation(
            cleanup_obj.cleanup_processing_rows)
        self._maintenance_thread.register_operation(full_sync.full_sync)
        self._maintenance_thread.register_operation(recovery.journal_recovery)
        self._maintenance_thread.start()

    @staticmethod
    def _record_in_journal(context, object_type, operation, data=None):
        if data is None:
            data = context.current
        journal.record(context._plugin_context, context, object_type,
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

    def _make_security_group_dict(self, sg):
        return {
            'id': sg['id'],
            'name': sg['name'],
            'tenant_id': sg['tenant_id'],
            'description': sg['description']
        }

    def _make_security_group_rule_dict(self, rule, sg_id=None):
        if sg_id is None:
            sg_id = rule['security_group_id']
        return {
            'id': rule['id'],
            'tenant_id': rule['tenant_id'],
            'security_group_id': sg_id,
            'ethertype': rule['ethertype'],
            'direction': rule['direction'],
            'protocol': rule['protocol'],
            'port_range_min': rule['port_range_min'],
            'port_range_max': rule['port_range_max'],
            'remote_ip_prefix': rule['remote_ip_prefix'],
            'remote_group_id': rule['remote_group_id']
        }

    def _sync_security_group_create_precommit(
            self, context, operation, object_type, res_id, resource_dict):
        # TODO(yamahata): remove this work around once
        # https://review.openstack.org/#/c/281693/
        # is merged.
        # For now, SG rules aren't passed down with
        # precommit event. We resort to get it by query.
        new_objects = context.session.new
        sgs = [sg for sg in new_objects
               if isinstance(sg, securitygroup.SecurityGroup)]
        if res_id is not None:
            sgs = [sg for sg in sgs if sg.id == res_id]
        for sg in sgs:
            sg_id = sg['id']
            res = self._make_security_group_dict(sg)
            journal.record(context, None, object_type, sg_id, operation, res)
            # NOTE(yamahata): when security group is created, default rules
            # are also created.
            # NOTE(yamahata): at this point, rule.security_group_id isn't
            # populated. but it has rule.security_group
            rules = [rule for rule in new_objects
                     if (isinstance(rule, securitygroup.SecurityGroupRule) and
                         rule.security_group == sg)]
            for rule in rules:
                res_rule = self._make_security_group_rule_dict(rule, sg_id)
                journal.record(context, None, odl_const.ODL_SG_RULE,
                               rule['id'], odl_const.ODL_CREATE, res_rule)

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

        # NOTE(yamahata): in security group/security gorup rule case,
        # orm object is passed. not resource dict. So we have to convert it
        # into resource_dict
        if not isinstance(resource_dict, dict) and resource_dict is not None:
            if object_type == odl_const.ODL_SG:
                resource_dict = self._make_security_group_dict(resource_dict)
            elif object_type == odl_const.ODL_SG_RULE:
                resource_dict = self._make_security_group_rule_dict(
                    resource_dict)
        # NOTE(yamahata): bug work around
        # callback for update of security grouop doesn't pass complete
        # info. So we have to build it. Once the bug is fixed, remove
        # this bug work around.
        # https://launchpad.net/bugs/1546910
        # https://review.openstack.org/#/c/281693/
        elif (object_type == odl_const.ODL_SG and
              operation == odl_const.ODL_UPDATE):
            # NOTE(yamahata): precommit_update is called before updating
            # values. so context.session.{new, dirty} doesn't include sg
            # in question. a dictionary with new values needs to be build.
            core_plugin = directory.get_plugin()
            sg = core_plugin._get_security_group(context, res_id)
            tmp_dict = self._make_security_group_dict(sg)
            tmp_dict.update(resource_dict)
            resource_dict = tmp_dict

        object_uuid = (resource_dict.get('id')
                       if operation == 'create' else res_id)
        if object_uuid is None:
            # NOTE(yamahata): bug work around bug/1546910
            # TODO(yamahata): once the following patch is merged
            # remove this bug work around
            # https://review.openstack.org/#/c/281693/
            assert object_type == odl_const.ODL_SG_RULE
            # NOTE(yamahata): bulk creation case
            # context.session.new accumulates all newly created orm object.
            # there is no easy way to pick up the lastly added orm object.
            rules = [rule for rule in context.session.new
                     if (isinstance(rule, securitygroup.SecurityGroupRule))]
            if len(rules) == 1:
                object_uuid = rules[0].id
                resource_dict['id'] = object_uuid
            else:
                LOG.error(_LE("bulk creation of sgrule isn't supported"))
                raise NotImplementedError(
                    _("unsupporetd bulk creation of security group rule"))
        journal.record(context, None, object_type, object_uuid,
                       operation, resource_dict)
        # NOTE(yamahata): DB auto deletion
        # Security Group Rule under this Security Group needs to
        # be deleted. At NeutronDB layer rules are auto deleted with
        # cascade='all,delete'.
        if (object_type == odl_const.ODL_SG and
                operation == odl_const.ODL_DELETE):
            for rule in kwargs['security_group'].rules:
                journal.record(context, None, odl_const.ODL_SG_RULE,
                               rule.id, odl_const.ODL_DELETE, [object_uuid])

    def sync_from_callback_postcommit(self, context, operation, res_type,
                                      res_id, resource_dict, **kwargs):
        self._postcommit(context)

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
        segments = network.get(mpnet.SEGMENTS)
        if segments is None:
            return True
        return all(segment[providernet.NETWORK_TYPE]
                   in VLAN_TRANSPARENT_NETWORK_TYPES
                   for segment in segments)
