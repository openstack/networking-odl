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

import requests

from neutron import context as neutron_context
from neutron_lib import constants
from neutron_lib.plugins import directory

from networking_odl.common import client
from networking_odl.common import constants as odl_const
from networking_odl.db import db

# Define which pending operation types should be deleted
_CANARY_NETWORK_ID = "bd8db3a8-2b30-4083-a8b3-b3fd46401142"
_CANARY_TENANT_ID = "bd8db3a8-2b30-4083-a8b3-b3fd46401142"
_CANARY_NETWORK_DATA = {'id': _CANARY_NETWORK_ID,
                        'tenant_id': _CANARY_TENANT_ID,
                        'name': 'Sync Canary Network',
                        'admin_state_up': False}
_OPS_TO_DELETE_ON_SYNC = (odl_const.ODL_CREATE, odl_const.ODL_UPDATE)
_CLIENT = client.OpenDaylightRestClientGlobal()


def full_sync(session):
    if not _full_sync_needed(session):
        return

    db.delete_pending_rows(session, _OPS_TO_DELETE_ON_SYNC)

    dbcontext = neutron_context.get_admin_context()
    plugin = directory.get_plugin()
    for resource_type, collection_name in odl_const.L2_RESOURCES.items():
        _sync_resources(session, plugin, dbcontext, resource_type,
                        collection_name)

    l3plugin = directory.get_plugin(constants.L3)
    for resource_type, collection_name in odl_const.L3_RESOURCES.items():
        _sync_resources(session, l3plugin, dbcontext, resource_type,
                        collection_name)

    db.create_pending_row(session, odl_const.ODL_NETWORK, _CANARY_NETWORK_ID,
                          odl_const.ODL_CREATE, _CANARY_NETWORK_DATA)


def _full_sync_needed(session):
    return (_canary_network_missing_on_odl() and
            _canary_network_not_in_journal(session))


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


def _canary_network_not_in_journal(session):
    return not db.check_for_pending_or_processing_ops(
        session, _CANARY_NETWORK_ID, operation=odl_const.ODL_CREATE)


def _sync_resources(session, plugin, dbcontext, object_type, collection_name):
    obj_getter = getattr(plugin, 'get_%s' % collection_name)
    resources = obj_getter(dbcontext)

    for resource in resources:
        db.create_pending_row(session, object_type, resource['id'],
                              odl_const.ODL_CREATE, resource)
