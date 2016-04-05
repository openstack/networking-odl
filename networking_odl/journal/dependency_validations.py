# Copyright (c) 2015 OpenStack Foundation
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

from networking_odl.common import constants as odl_const
from networking_odl.db import db


def _is_valid_update_operation(session, row):
    # Check if there are older updates in the queue
    if db.check_for_older_ops(session, row):
        return False

    # Check for a pending or processing create operation on this uuid
    if db.check_for_pending_or_processing_ops(
            session, row.object_uuid, odl_const.ODL_CREATE):
        return False
    return True


def validate_network_operation(session, row):
    """Validate the network operation based on dependencies.

    Validate network operation depending on whether it's dependencies
    are still in 'pending' or 'processing' state. e.g.
    """
    if row.operation == odl_const.ODL_DELETE:
        # Check for any pending or processing create or update
        # ops on this uuid itself
        if db.check_for_pending_or_processing_ops(
            session, row.object_uuid, [odl_const.ODL_UPDATE,
                                       odl_const.ODL_CREATE]):
            return False
        # Check for dependent operations
        if db.check_for_pending_delete_ops_with_parent(
            session, odl_const.ODL_SUBNET, row.object_uuid):
            return False
        if db.check_for_pending_delete_ops_with_parent(
            session, odl_const.ODL_PORT, row.object_uuid):
            return False
        if db.check_for_pending_delete_ops_with_parent(
            session, odl_const.ODL_ROUTER, row.object_uuid):
            return False
    elif (row.operation == odl_const.ODL_UPDATE and
            not _is_valid_update_operation(session, row)):
        return False
    return True


def validate_subnet_operation(session, row):
    """Validate the subnet operation based on dependencies.

    Validate subnet operation depending on whether it's dependencies
    are still in 'pending' or 'processing' state. e.g.
    """
    if row.operation in (odl_const.ODL_CREATE, odl_const.ODL_UPDATE):
        network_id = row.data['network_id']
        # Check for pending or processing network operations
        if db.check_for_pending_or_processing_ops(session, network_id):
            return False
        if (row.operation == odl_const.ODL_UPDATE and
                not _is_valid_update_operation(session, row)):
            return False
    elif row.operation == odl_const.ODL_DELETE:
        # Check for any pending or processing create or update
        # ops on this uuid itself
        if db.check_for_pending_or_processing_ops(
            session, row.object_uuid, [odl_const.ODL_UPDATE,
                                       odl_const.ODL_CREATE]):
            return False
        # Check for dependent operations
        if db.check_for_pending_delete_ops_with_parent(
            session, odl_const.ODL_PORT, row.object_uuid):
            return False

    return True


def validate_port_operation(session, row):
    """Validate port operation based on dependencies.

    Validate port operation depending on whether it's dependencies
    are still in 'pending' or 'processing' state. e.g.
    """
    if row.operation in (odl_const.ODL_CREATE, odl_const.ODL_UPDATE):
        network_id = row.data['network_id']
        # Check for pending or processing network operations
        ops = db.check_for_pending_or_processing_ops(session, network_id)
        # Check for pending subnet operations.
        for fixed_ip in row.data['fixed_ips']:
            ip_ops = db.check_for_pending_or_processing_ops(
                session, fixed_ip['subnet_id'])
            ops = ops or ip_ops

        if ops:
            return False
        if (row.operation == odl_const.ODL_UPDATE and
                not _is_valid_update_operation(session, row)):
            return False
    elif row.operation == odl_const.ODL_DELETE:
        # Check for any pending or processing create or update
        # ops on this uuid itself
        if db.check_for_pending_or_processing_ops(
            session, row.object_uuid, [odl_const.ODL_UPDATE,
                                       odl_const.ODL_CREATE]):
            return False

    return True


def validate_router_operation(session, row):
    """Validate router operation based on dependencies.

    Validate router operation depending on whether it's dependencies
    are still in 'pending' or 'processing' state.
    """
    if row.operation in (odl_const.ODL_CREATE, odl_const.ODL_UPDATE):
        if row.data['gw_port_id'] is not None:
            if db.check_for_pending_or_processing_ops(session,
                                                      row.data['gw_port_id']):
                return False
        if (row.operation == odl_const.ODL_UPDATE and
                not _is_valid_update_operation(session, row)):
            return False
    elif row.operation == odl_const.ODL_DELETE:
        # Check for any pending or processing create or update
        # operations on this uuid.
        if db.check_for_pending_or_processing_ops(session, row.object_uuid,
                                                  [odl_const.ODL_UPDATE,
                                                   odl_const.ODL_CREATE]):
            return False

        # Check that dependent port delete operation has completed.
        if db.check_for_pending_delete_ops_with_parent(
            session, odl_const.ODL_PORT, row.object_uuid):
            return False

        # Check that dependent floatingip delete operation has completed.
        if db.check_for_pending_delete_ops_with_parent(
                session, odl_const.ODL_FLOATINGIP, row.object_uuid):
            return False

        # Check that dependent router interface remove operation has completed.
        if db.check_for_pending_remove_ops_with_parent(
                session, row.object_uuid):
            return False

    return True


def validate_floatingip_operation(session, row):
    """Validate floatingip operation based on dependencies.

    Validate floating IP operation depending on whether it's dependencies
    are still in 'pending' or 'processing' state.
    """
    if row.operation in (odl_const.ODL_CREATE, odl_const.ODL_UPDATE):
        network_id = row.data.get('floating_network_id')
        if network_id is not None:
            if not db.check_for_pending_or_processing_ops(session, network_id):
                port_id = row.data.get('port_id')
                if port_id is not None:
                    if db.check_for_pending_or_processing_ops(session,
                                                              port_id):
                        return False
            else:
                return False

        router_id = row.data.get('router_id')
        if router_id is not None:
            if db.check_for_pending_or_processing_ops(session, router_id):
                return False
        if (row.operation == odl_const.ODL_UPDATE and
                not _is_valid_update_operation(session, row)):
            return False
    elif row.operation == odl_const.ODL_DELETE:
        # Check for any pending or processing create or update
        # ops on this uuid itself
        if db.check_for_pending_or_processing_ops(session, row.object_uuid,
                                                  [odl_const.ODL_UPDATE,
                                                   odl_const.ODL_CREATE]):
            return False

    return True


def validate_router_interface_operation(session, row):
    """Validate router_interface operation based on dependencies.

    Validate router_interface operation depending on whether it's dependencies
    are still in 'pending' or 'processing' state.
    """
    if row.operation == odl_const.ODL_ADD:
        # Verify that router event has been completed.
        if db.check_for_pending_or_processing_ops(session, row.data['id']):
            return False

        # TODO(rcurran): Check for port_id?
        if db.check_for_pending_or_processing_ops(session,
                                                  row.data['subnet_id']):
            return False
    elif row.operation == odl_const.ODL_REMOVE:
        if db.check_for_pending_or_processing_add(session, row.data['id'],
                                                  row.data['subnet_id']):
            return False

    return True


def validate_security_group_operation(session, row):
    """Validate security_group operation based on dependencies.

    Validate security_group operation depending on whether it's dependencies
    are still in 'pending' or 'processing' state. e.g.
    """
    return True


def validate_security_group_rule_operation(session, row):
    """Validate security_group_rule operation based on dependencies.

    Validate security_group_rule operation depending on whether it's
    dependencies are still in 'pending' or 'processing' state. e.g.
    """
    return True

VALIDATION_MAP = {
    odl_const.ODL_NETWORK: validate_network_operation,
    odl_const.ODL_SUBNET: validate_subnet_operation,
    odl_const.ODL_PORT: validate_port_operation,
    odl_const.ODL_ROUTER: validate_router_operation,
    odl_const.ODL_ROUTER_INTF: validate_router_interface_operation,
    odl_const.ODL_FLOATINGIP: validate_floatingip_operation,
    odl_const.ODL_SG: validate_security_group_operation,
    odl_const.ODL_SG_RULE: validate_security_group_rule_operation,
}
