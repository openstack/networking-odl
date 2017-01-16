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

from networking_odl._i18n import _
from networking_odl.common import constants as odl_const
from networking_odl.db import db


def _is_valid_update_operation(session, row):
    """Validate that an update operation has no older operations.

    An update is valid iff there aren't any older update or create operations
    on the same object (determined by type and ID).
    """
    # Check if there are older updates in the queue
    if db.check_for_older_ops(session, row):
        return False

    # Check for a pending or processing create operation on this uuid
    if db.check_for_pending_or_processing_ops(
            session, row.object_uuid, operation=odl_const.ODL_CREATE):
        return False
    return True


def _is_valid_delete_operation(session, row):
    """Validate that a delete operation has no dependent operations.

    A delete is valid if it has no older update or create operations.
    Additionally the row might contain other resource IDs which the delete
    should depend on, in which case the delete is valid if none of the
    dependent objects has delete operations.
    """
    # Check for any pending or processing create or update
    # ops on the row itself
    if db.check_for_pending_or_processing_ops(
        session, row.object_uuid, operation=[odl_const.ODL_UPDATE,
                                             odl_const.ODL_CREATE]):
        return False

    # Check for dependent operations
    dependent_resource_types = _DELETE_DEPENDENCIES.get(row.object_type)
    if dependent_resource_types is not None:
        for resource_type in dependent_resource_types:
            if db.check_for_pending_delete_ops_with_parent(
                    session, resource_type, row.object_uuid):
                return False
    return True


def _no_older_operations(session, object_id, row):
    """Check that no older operation exist.

    Determine that there aren't any operations still in the queue for the
    given ID(s) that are older than the one in the given row.
    If such an operation is found, False is returned.
    If no older operations exist, True is returned.
    """
    if not isinstance(object_id, (list, tuple)):
        object_id = (object_id,)

    for object_id in object_id:
        if db.check_for_pending_or_processing_ops(
                session, object_id, seqnum=row.seqnum):
            return False

    return True


def _generate_sunbet_deps(row):
    return row.data['network_id']


def _generate_port_deps(row):
    subnet_ids = [fixed_ip['subnet_id'] for fixed_ip in row.data['fixed_ips']]
    return [row.data['network_id']] + subnet_ids


def _generate_router_deps(row):
    return row.data['gw_port_id']


def _generate_floatingip_deps(row):
    object_ids = []
    network_id = row.data.get('floating_network_id')
    if network_id is not None:
        object_ids.append(network_id)

    port_id = row.data.get('port_id')
    if port_id is not None:
        object_ids.append(port_id)

    router_id = row.data.get('router_id')
    if router_id is not None:
        object_ids.append(router_id)

    return object_ids


def _generate_trunk_deps(row):
    portids = [subport['port_id'] for subport in row.data['sub_ports']]
    portids.append(row.data['port_id'])
    return portids

_CREATE_OR_UPDATE_DEP_GENERATOR = {
    odl_const.ODL_SUBNET: _generate_sunbet_deps,
    odl_const.ODL_PORT: _generate_port_deps,
    odl_const.ODL_ROUTER: _generate_router_deps,
    odl_const.ODL_FLOATINGIP: _generate_floatingip_deps,
    odl_const.ODL_TRUNK: _generate_trunk_deps,
}


_DELETE_DEPENDENCIES = {
    odl_const.ODL_NETWORK: (odl_const.ODL_SUBNET, odl_const.ODL_PORT,
                            odl_const.ODL_ROUTER),
    odl_const.ODL_SUBNET: (odl_const.ODL_PORT,),
    odl_const.ODL_ROUTER: (odl_const.ODL_PORT, odl_const.ODL_FLOATINGIP),
    odl_const.ODL_PORT: (odl_const.ODL_TRUNK,),
}


def validate(session, row):
    """Validate resource dependency in journaled operations.

    As a rule of thumb validation takes into consideration only operations in
    pending or processing state, other states are irrelevant.
    :param session: db session
    :param row: entry in journal entry to be validated
    """
    if row.operation == odl_const.ODL_DELETE:
        return _is_valid_delete_operation(session, row)
    elif row.operation == odl_const.ODL_UPDATE:
        # If the update itself isn't valid fail before checking possible
        # dependent operations.
        if not _is_valid_update_operation(session, row):
            return False
    elif row.operation != odl_const.ODL_CREATE:
        raise ValueError(_("unsupported operation {}").format(row.operation))

    # Validate dependencies if there are any to validate.
    dep_generator = _CREATE_OR_UPDATE_DEP_GENERATOR.get(row.object_type)
    if dep_generator is not None:
        object_ids = dep_generator(row)
        if object_ids is not None:
            return _no_older_operations(session, object_ids, row)

    return True
