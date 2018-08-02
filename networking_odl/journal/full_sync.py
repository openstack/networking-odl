#
# Copyright (C) 2016 Red Hat, Inc.
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

from neutron.db import api as db_api
from neutron_lib.db import api as lib_db_api
from neutron_lib.plugins import directory
import requests

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.db import db
from networking_odl.journal import base_driver
from networking_odl.journal import journal

# Define which pending operation types should be deleted
_CANARY_NETWORK_ID = "bd8db3a8-2b30-4083-a8b3-b3fd46401142"
_CANARY_TENANT_ID = "bd8db3a8-2b30-4083-a8b3-b3fd46401142"
_CANARY_NETWORK_DATA = {'id': _CANARY_NETWORK_ID,
                        'tenant_id': _CANARY_TENANT_ID,
                        'name': 'Sync Canary Network',
                        'admin_state_up': False}
_OPS_TO_DELETE_ON_SYNC = (odl_const.ODL_CREATE, odl_const.ODL_UPDATE)
_CLIENT = client.OpenDaylightRestClientGlobal()

_ORDERED_ODL_RESOURCES = (
    odl_const.ODL_SG,
    odl_const.ODL_SG_RULE,
    odl_const.ODL_NETWORK,
    odl_const.ODL_SUBNET,
    odl_const.ODL_ROUTER,
    odl_const.ODL_PORT,
    odl_const.ODL_FLOATINGIP,
    odl_const.ODL_LOADBALANCER,
    odl_const.ODL_LISTENER,
    odl_const.ODL_POOL,
    odl_const.ODL_MEMBER,
    odl_const.ODL_HEALTHMONITOR,
    odl_const.ODL_QOS_POLICY,
    odl_const.ODL_TRUNK,
    odl_const.ODL_BGPVPN,
    odl_const.ODL_BGPVPN_NETWORK_ASSOCIATION,
    odl_const.ODL_BGPVPN_ROUTER_ASSOCIATION,
    odl_const.ODL_SFC_FLOW_CLASSIFIER,
    odl_const.ODL_SFC_PORT_PAIR,
    odl_const.ODL_SFC_PORT_PAIR_GROUP,
    odl_const.ODL_SFC_PORT_CHAIN,
    odl_const.ODL_L2GATEWAY,
    odl_const.ODL_L2GATEWAY_CONNECTION,
)


# TODO(rajivk): Remove this variable, while fixing recovery
ALL_RESOURCES = {}

FULL_SYNC_RESOURCES = {}


def register(driver, resources, handler=None):
    def default_handler(context, resource_type):
        return get_resources(context, driver, resources[resource_type])

    ALL_RESOURCES[driver] = resources
    handler = handler or default_handler
    for resource in resources:
        FULL_SYNC_RESOURCES[resource] = handler


@lib_db_api.retry_if_session_inactive()
@db_api.context_manager.writer.savepoint
def full_sync(context):
    if not _full_sync_needed(context):
        return

    db.delete_pending_rows(context, _OPS_TO_DELETE_ON_SYNC)

    for resource_type in _ORDERED_ODL_RESOURCES:
        handler = FULL_SYNC_RESOURCES.get(resource_type)
        if handler:
            _sync_resources(context, resource_type, handler)

    journal.record(context, odl_const.ODL_NETWORK, _CANARY_NETWORK_ID,
                   odl_const.ODL_CREATE, _CANARY_NETWORK_DATA)


def _full_sync_needed(context):
    return (_canary_network_missing_on_odl() and
            _canary_network_not_in_journal(context))


def _canary_network_missing_on_odl():
    # Try to reach the ODL server, sometimes it might be up & responding to
    # HTTP calls but inoperative..
    client = _CLIENT.get_client()
    response = client.get(odl_const.ODL_NETWORKS)
    response.raise_for_status()

    response = client.get(odl_const.ODL_NETWORKS + "/" + _CANARY_NETWORK_ID)
    if response.status_code == requests.codes.not_found:
        return True

    # In case there was an error raise it up because we don't know how to deal
    # with it..
    response.raise_for_status()
    return False


def _canary_network_not_in_journal(context):
    return not db.get_pending_or_processing_ops(
        context, _CANARY_NETWORK_ID, operation=odl_const.ODL_CREATE)


def get_resources_require_id(plugin, context, get_resources_for_id,
                             method_name_for_resource):

    dep_id_resources = get_resources_for_id(context)
    resources = []
    for d_resource in dep_id_resources:
        obj_getter = getattr(plugin, method_name_for_resource)
        resource = obj_getter(context, d_resource['id'])
        if resource:
            resources.extend(resource)

    return resources


def get_resources(context, plugin_type, resource_type):
    plugin = directory.get_plugin(plugin_type)
    obj_getter = getattr(plugin, 'get_%s' % resource_type)
    return obj_getter(context)


def _sync_resources(context, object_type, handler):
    resources = handler(context, object_type)
    for resource in resources:
        journal.record(context, object_type, resource['id'],
                       odl_const.ODL_CREATE, resource)


@lib_db_api.retry_if_session_inactive()
# TODO(rajivk): Change name from sync_resource to _sync_resources
# once, we are completely moved to new sync mechanism to plug new syncing
# mechanism.
def sync_resources(context, resource_type):
    driver = base_driver.get_driver(resource_type)
    resources = driver.get_resources_for_full_sync(context, resource_type)
    with db_api.context_manager.writer.savepoint.using(context):
        for resource in resources:
            journal.record(context, resource_type, resource['id'],
                           odl_const.ODL_CREATE, resource)
