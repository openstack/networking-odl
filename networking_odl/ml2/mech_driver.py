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
from oslo_utils import excutils
import requests

from neutron.common import exceptions as n_exc
from neutron.common import utils

from networking_odl.common import client as odl_client
from networking_odl.common import constants as odl_const
from networking_odl.common import utils as odl_utils

LOG = logging.getLogger(__name__)

not_found_exception_map = {odl_const.ODL_NETWORKS: n_exc.NetworkNotFound,
                           odl_const.ODL_SUBNETS: n_exc.SubnetNotFound,
                           odl_const.ODL_PORTS: n_exc.PortNotFound}


class OpenDaylightDriver(object):

    """OpenDaylight Python Driver for Neutron.

    This code is the backend implementation for the OpenDaylight ML2
    MechanismDriver for OpenStack Neutron.
    """
    out_of_sync = True

    def __init__(self):
        LOG.debug("Initializing OpenDaylight ML2 driver")
        self.client = odl_client.OpenDaylightRestClient(
            cfg.CONF.ml2_odl.url,
            cfg.CONF.ml2_odl.username,
            cfg.CONF.ml2_odl.password,
            cfg.CONF.ml2_odl.timeout
        )

    def synchronize(self, operation, object_type, context):
        """Synchronize ODL with Neutron following a configuration change."""
        if self.out_of_sync:
            self.sync_full(context)
        else:
            self.sync_single_resource(operation, object_type, context)

    @staticmethod
    def filter_create_network_attributes(network, context):
        """Filter out network attributes not required for a create."""
        odl_utils.try_del(network, ['status', 'subnets', 'vlan_transparent',
                          'mtu'])

    @staticmethod
    def filter_create_subnet_attributes(subnet, context):
        """Filter out subnet attributes not required for a create."""
        pass

    @classmethod
    def filter_create_port_attributes(cls, port, context):
        """Filter out port attributes not required for a create."""
        cls.add_security_groups(port, context)
        # TODO(kmestery): Converting to uppercase due to ODL bug
        # https://bugs.opendaylight.org/show_bug.cgi?id=477
        port['mac_address'] = port['mac_address'].upper()
        odl_utils.try_del(port, ['status'])

    def sync_resources(self, collection_name, context):
        """Sync objects from Neutron over to OpenDaylight.

        This will handle syncing networks, subnets, and ports from Neutron to
        OpenDaylight. It also filters out the requisite items which are not
        valid for create API operations.
        """
        to_be_synced = []
        dbcontext = context._plugin_context
        obj_getter = getattr(context._plugin, 'get_%s' % collection_name)
        resources = obj_getter(dbcontext)
        for resource in resources:
            try:
                urlpath = collection_name + '/' + resource['id']
                self.client.sendjson('get', urlpath, None)
            except requests.exceptions.HTTPError as e:
                with excutils.save_and_reraise_exception() as ctx:
                    if e.response.status_code == requests.codes.not_found:
                        attr_filter = self.create_object_map[collection_name]
                        attr_filter(resource, context)
                        to_be_synced.append(resource)
                        ctx.reraise = False
        key = collection_name[:-1] if len(to_be_synced) == 1 else (
            collection_name)
        self.client.sendjson('post', collection_name, {key: to_be_synced})

    @utils.synchronized('odl-sync-full')
    def sync_full(self, context):
        """Resync the entire database to ODL.

        Transition to the in-sync state on success.
        Note: we only allow a single thread in here at a time.
        """
        if not self.out_of_sync:
            return
        for collection_name in [odl_const.ODL_NETWORKS,
                                odl_const.ODL_SUBNETS,
                                odl_const.ODL_PORTS]:
            self.sync_resources(collection_name, context)
        self.out_of_sync = False

    @staticmethod
    def filter_update_network_attributes(network, context):
        """Filter out network attributes for an update operation."""
        odl_utils.try_del(network, ['id', 'status', 'subnets', 'tenant_id',
                          'vlan_transparent', 'mtu'])

    @staticmethod
    def filter_update_subnet_attributes(subnet, context):
        """Filter out subnet attributes for an update operation."""
        odl_utils.try_del(subnet, ['id', 'network_id', 'ip_version', 'cidr',
                          'allocation_pools', 'tenant_id'])

    @classmethod
    def filter_update_port_attributes(cls, port, context):
        """Filter out port attributes for an update operation."""
        cls.add_security_groups(port, context)
        odl_utils.try_del(port, ['network_id', 'id', 'status', 'mac_address',
                          'tenant_id', 'fixed_ips'])

    def sync_single_resource(self, operation, object_type, context):
        """Sync over a single resource from Neutron to OpenDaylight.

        Handle syncing a single operation over to OpenDaylight, and correctly
        filter attributes out which are not required for the requisite
        operation (create or update) being handled.
        """
        try:
            obj_id = context.current['id']
            if operation == 'delete':
                self.client.sendjson('delete', object_type + '/' + obj_id,
                                     None)
            else:
                if operation == 'create':
                    urlpath = object_type
                    method = 'post'
                    attr_filter = self.create_object_map[object_type]
                elif operation == 'update':
                    urlpath = object_type + '/' + obj_id
                    method = 'put'
                    attr_filter = self.update_object_map[object_type]
                resource = context.current.copy()
                attr_filter(resource, context)
                self.client.sendjson(method, urlpath,
                                     {object_type[:-1]: resource})
        except Exception:
            with excutils.save_and_reraise_exception():
                self.out_of_sync = True

    @staticmethod
    def add_security_groups(port, context):
        """Populate the 'security_groups' field with entire records."""
        dbcontext = context._plugin_context
        groups = [context._plugin.get_security_group(dbcontext, sg)
                  for sg in port['security_groups']]
        port['security_groups'] = groups

OpenDaylightDriver.create_object_map = {
    odl_const.ODL_NETWORKS:
        OpenDaylightDriver.filter_create_network_attributes,
    odl_const.ODL_SUBNETS:
        OpenDaylightDriver.filter_create_subnet_attributes,
    odl_const.ODL_PORTS:
        OpenDaylightDriver.filter_create_port_attributes}

OpenDaylightDriver.update_object_map = {
    odl_const.ODL_NETWORKS:
        OpenDaylightDriver.filter_update_network_attributes,
    odl_const.ODL_SUBNETS:
        OpenDaylightDriver.filter_update_subnet_attributes,
    odl_const.ODL_PORTS:
        OpenDaylightDriver.filter_update_port_attributes}
