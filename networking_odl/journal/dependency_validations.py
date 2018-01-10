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


def _get_delete_dependencies(session, object_type, object_uuid):
    """Get dependent operations for a delete operation.

    Return any operations that pertain to the delete: Either create
    or update operations on the same object, or delete operations on other
    objects that depend on the deleted object.
    """
    # Get any pending or processing create or update ops on the row itself
    deps = db.get_pending_or_processing_ops(
        session, object_uuid, operation=(odl_const.ODL_UPDATE,
                                         odl_const.ODL_CREATE))

    # Get dependent operations of other dependent types
    dependent_resource_types = _DELETE_DEPENDENCIES.get(object_type)
    if dependent_resource_types is not None:
        for resource_type in dependent_resource_types:
            deps.extend(db.get_pending_delete_ops_with_parent(
                session, resource_type, object_uuid))

    return deps


def _get_older_operations(session, object_ids):
    """Get any older operations.

    Return any operations still in the queue for the given ID(s).
    """
    if not isinstance(object_ids, (list, tuple)):
        object_ids = (object_ids,)

    deps = []
    for object_id in object_ids:
        deps.extend(
            db.get_pending_or_processing_ops(session, object_id))

    return deps


def _generate_subnet_deps(data):
    return data['network_id']


def _generate_port_deps(data):
    object_ids = set(fixed_ip['subnet_id'] for fixed_ip in data['fixed_ips'])
    object_ids = list(object_ids)
    object_ids.append(data['network_id'])
    qos_policy_id = data.get('qos_policy_id')
    if qos_policy_id is not None:
        object_ids.append(qos_policy_id)
    return object_ids


def _generate_network_deps(data):
    return data.get('qos_policy_id')


def _generate_sg_rule_deps(data):
    return data['security_group_id']


def _generate_router_deps(data):
    return data['gw_port_id']


def _generate_floatingip_deps(data):
    object_ids = []
    network_id = data.get('floating_network_id')
    if network_id is not None:
        object_ids.append(network_id)

    port_id = data.get('port_id')
    if port_id is not None:
        object_ids.append(port_id)

    router_id = data.get('router_id')
    if router_id is not None:
        object_ids.append(router_id)

    return object_ids


def _generate_trunk_deps(data):
    portids = [subport['port_id'] for subport in data['sub_ports']]
    portids.append(data['port_id'])
    return portids


def _generate_l2gateway_connection_deps(data):
    object_ids = []
    network_id = data.get('network_id')
    if network_id is not None:
        object_ids.append(network_id)

    gateway_id = data.get('gateway_id')
    if gateway_id is not None:
        object_ids.append(gateway_id)

    return object_ids


def _generate_sfc_port_pair_deps(data):
    object_ids = []
    ingress_port = data.get('ingress')
    if ingress_port is not None:
        object_ids.append(ingress_port)

    egress_port = data.get('egress')
    if egress_port is not None:
        object_ids.append(egress_port)

    return object_ids


def _generate_sfc_port_pair_group_deps(data):
    return data['port_pairs']


def _generate_sfc_port_chain_deps(data):
    object_ids = data['port_pair_groups'][:]
    flow_classifiers = data['flow_classifiers'][:]
    object_ids.extend(flow_classifiers)

    return object_ids


def _generate_bgpvpn_deps(data):
    object_ids = []

    network_ids = data.get('networks')
    if network_ids is not None:
        object_ids.extend(network_ids)

    router_ids = data.get('routers')
    if router_ids is not None:
        object_ids.extend(router_ids)

    return object_ids


_CREATE_OR_UPDATE_DEP_GENERATOR = {
    odl_const.ODL_NETWORK: _generate_network_deps,
    odl_const.ODL_SUBNET: _generate_subnet_deps,
    odl_const.ODL_PORT: _generate_port_deps,
    # TODO(yamahata): dependency between SG and PORT
    odl_const.ODL_SG_RULE: _generate_sg_rule_deps,
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
    # TODO(yamahata): dependency between SG and PORT
    odl_const.ODL_SG: (odl_const.ODL_SG_RULE,),
    odl_const.ODL_L2GATEWAY: (odl_const.ODL_L2GATEWAY_CONNECTION,),
    odl_const.ODL_SFC_FLOW_CLASSIFIER: (odl_const.ODL_SFC_PORT_CHAIN,),
    odl_const.ODL_SFC_PORT_PAIR: (odl_const.ODL_SFC_PORT_PAIR_GROUP,),
    odl_const.ODL_SFC_PORT_PAIR_GROUP: (odl_const.ODL_SFC_PORT_CHAIN,),
    odl_const.ODL_QOS_POLICY: (odl_const.ODL_PORT, odl_const.ODL_NETWORK),
}


def calculate(session, operation, object_type, object_uuid, data):
    """Calculate resource deps in journaled operations.

    As a rule of thumb validation takes into consideration only operations in
    pending or processing state, other states are irrelevant.
    :param session: db session
    :param row: entry in journal entry to be validated
    """
    deps = []
    if operation == odl_const.ODL_DELETE:
        return _get_delete_dependencies(session, object_type, object_uuid)
    elif operation == odl_const.ODL_UPDATE:
        deps.extend(
            db.get_pending_or_processing_ops(
                session, object_uuid,
                operation=(odl_const.ODL_CREATE, odl_const.ODL_UPDATE)))
    elif operation != odl_const.ODL_CREATE:
        raise ValueError(_("unsupported operation {}").format(operation))

    # Validate deps if there are any to validate.
    dep_generator = _CREATE_OR_UPDATE_DEP_GENERATOR.get(object_type)
    if dep_generator is not None:
        object_ids = dep_generator(data)
        if object_ids is not None:
            deps.extend(_get_older_operations(session, object_ids))

    return deps
