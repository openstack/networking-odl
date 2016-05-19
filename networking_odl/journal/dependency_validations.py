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


def _generate_subnet_deps(row):
    return row.data['network_id']


def _generate_port_deps(row):
    object_ids = [fixed_ip['subnet_id'] for fixed_ip in row.data['fixed_ips']]
    object_ids.append(row.data['network_id'])
    qos_policy_id = row.data.get('qos_policy_id')
    if qos_policy_id is not None:
        object_ids.append(qos_policy_id)
    return object_ids


def _generate_network_deps(row):
    return row.data.get('qos_policy_id')


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


def _generate_l2gateway_connection_deps(row):
    object_ids = []
    network_id = row.data.get('network_id')
    if network_id is not None:
        object_ids.append(network_id)

    gateway_id = row.data.get('gateway_id')
    if gateway_id is not None:
        object_ids.append(gateway_id)

    return object_ids


def _generate_sfc_port_pair_deps(row):
    object_ids = []
    ingress_port = row.data.get('ingress')
    if ingress_port is not None:
        object_ids.append(ingress_port)

    egress_port = row.data.get('egress')
    if egress_port is not None:
        object_ids.append(egress_port)

    return object_ids


def _generate_sfc_port_pair_group_deps(row):
    port_pairs = [port_pair['id'] for port_pair in row.data['port_pairs']]
    return port_pairs


def _generate_sfc_port_chain_deps(row):
    object_ids = [port_pair_group['id'] for port_pair_group in
                  row.data['port_pair_groups']]
    flow_classifiers = [flow_classifier['id'] for flow_classifier in
                        row.data['flow_classifiers']]
    object_ids.extend(flow_classifiers)

    return object_ids


def _generate_bgpvpn_deps(row):
    object_ids = []

    network_ids = row.data.get('networks')
    if network_ids is not None:
        object_ids.extend(network_ids)

    router_ids = row.data.get('routers')
    if router_ids is not None:
        object_ids.extend(router_ids)

    return object_ids


_CREATE_OR_UPDATE_DEP_GENERATOR = {
    odl_const.ODL_NETWORK: _generate_network_deps,
    odl_const.ODL_SUBNET: _generate_subnet_deps,
    odl_const.ODL_PORT: _generate_port_deps,
    odl_const.ODL_ROUTER: _generate_router_deps,
    odl_const.ODL_FLOATINGIP: _generate_floatingip_deps,
    odl_const.ODL_TRUNK: _generate_trunk_deps,
    odl_const.ODL_L2GATEWAY_CONNECTION: _generate_l2gateway_connection_deps,
    odl_const.ODL_SFC_PORT_PAIR: _generate_sfc_port_pair_deps,
    odl_const.ODL_SFC_PORT_PAIR_GROUP: _generate_sfc_port_pair_group_deps,
    odl_const.ODL_SFC_PORT_CHAIN: _generate_sfc_port_chain_deps,
    odl_const.ODL_BGPVPN: _generate_bgpvpn_deps,
}


_DELETE_DEPENDENCIES = {
    odl_const.ODL_NETWORK: (odl_const.ODL_SUBNET, odl_const.ODL_PORT,
                            odl_const.ODL_ROUTER,
                            odl_const.ODL_L2GATEWAY_CONNECTION,
                            odl_const.ODL_BGPVPN),
    odl_const.ODL_SUBNET: (odl_const.ODL_PORT,),
    odl_const.ODL_ROUTER: (odl_const.ODL_PORT, odl_const.ODL_FLOATINGIP,
                           odl_const.ODL_BGPVPN),
    odl_const.ODL_PORT: (odl_const.ODL_TRUNK,),
    odl_const.ODL_L2GATEWAY: (odl_const.ODL_L2GATEWAY_CONNECTION,),
    odl_const.ODL_SFC_FLOW_CLASSIFIER: (odl_const.ODL_SFC_PORT_CHAIN,),
    odl_const.ODL_SFC_PORT_PAIR: (odl_const.ODL_SFC_PORT_PAIR_GROUP,),
    odl_const.ODL_SFC_PORT_PAIR_GROUP: (odl_const.ODL_SFC_PORT_CHAIN,),
    odl_const.ODL_QOS_POLICY: (odl_const.ODL_PORT, odl_const.ODL_NETWORK),
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
