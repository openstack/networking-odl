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

import abc
import copy
import six

import netaddr
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
import requests

from neutron.common import exceptions as n_exc
from neutron.common import utils
from neutron import context as neutron_context
from neutron.extensions import allowedaddresspairs as addr_pair
from neutron.extensions import securitygroup as sg
from neutron.plugins.ml2 import driver_api
from neutron.plugins.ml2 import driver_context

from networking_odl._i18n import _LE
from networking_odl.common import callback as odl_call
from networking_odl.common import client as odl_client
from networking_odl.common import constants as odl_const
from networking_odl.common import utils as odl_utils
from networking_odl.ml2 import port_binding


cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = logging.getLogger(__name__)

not_found_exception_map = {odl_const.ODL_NETWORKS: n_exc.NetworkNotFound,
                           odl_const.ODL_SUBNETS: n_exc.SubnetNotFound,
                           odl_const.ODL_PORTS: n_exc.PortNotFound,
                           odl_const.ODL_SGS: sg.SecurityGroupNotFound,
                           odl_const.ODL_SG_RULES:
                               sg.SecurityGroupRuleNotFound}


@six.add_metaclass(abc.ABCMeta)
class ResourceFilterBase(object):
    @staticmethod
    @abc.abstractmethod
    def filter_create_attributes(resource, context):
        pass

    @staticmethod
    @abc.abstractmethod
    def filter_update_attributes(resource, context):
        pass

    @staticmethod
    @abc.abstractmethod
    def filter_create_attributes_with_plugin(resource, plugin, dbcontext):
        pass


class NetworkFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(network, context):
        """Filter out network attributes not required for a create."""
        odl_utils.try_del(network, ['status', 'subnets'])

    @staticmethod
    def filter_update_attributes(network, context):
        """Filter out network attributes for an update operation."""
        odl_utils.try_del(network, ['id', 'status', 'subnets', 'tenant_id'])

    @classmethod
    def filter_create_attributes_with_plugin(cls, network, plugin, dbcontext):
        context = driver_context.NetworkContext(plugin, dbcontext, network)
        cls.filter_create_attributes(network, context)


class SubnetFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(subnet, context):
        """Filter out subnet attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(subnet, context):
        """Filter out subnet attributes for an update operation."""
        odl_utils.try_del(subnet, ['id', 'network_id', 'ip_version', 'cidr',
                          'allocation_pools', 'tenant_id'])

    @classmethod
    def filter_create_attributes_with_plugin(cls, subnet, plugin, dbcontext):
        network = plugin.get_network(dbcontext, subnet['network_id'])
        context = driver_context.SubnetContext(plugin, dbcontext, subnet,
                                               network)
        cls.filter_create_attributes(subnet, context)


class PortFilter(ResourceFilterBase):
    @staticmethod
    def _add_security_groups(port, context):
        """Populate the 'security_groups' field with entire records."""
        dbcontext = context._plugin_context
        groups = [context._plugin.get_security_group(dbcontext, sg)
                  for sg in port['security_groups']]
        port['security_groups'] = groups

    @classmethod
    def _fixup_allowed_ipaddress_pairs(cls, allowed_address_pairs):
        """unify (ip address or network address) into network address"""
        for address_pair in allowed_address_pairs:
            ip_address = address_pair['ip_address']
            network_address = str(netaddr.IPNetwork(ip_address))
            address_pair['ip_address'] = network_address

    @staticmethod
    def _filter_unmapped_null(port):
        # NOTE(yamahata): bug work around
        # https://bugs.eclipse.org/bugs/show_bug.cgi?id=475475
        #   Null-value for an unmapped element causes next mapped
        #   collection to contain a null value
        #   JSON: { "unmappedField": null, "mappedCollection": [ "a" ] }
        #
        #   Java Object:
        #   class Root {
        #     Collection<String> mappedCollection = new ArrayList<String>;
        #   }
        #
        #   Result:
        #   Field B contains one element; null
        #
        # TODO(yamahata): update along side with neutron and ODL
        #   add when neutron adds more extensions
        #   delete when ODL neutron northbound supports it
        # TODO(yamahata): do same thing for other resources
        unmapped_keys = ['dns_name', 'port_security_enabled',
                         'binding:profile']
        keys_to_del = [key for key in unmapped_keys if port.get(key) is None]
        if keys_to_del:
            odl_utils.try_del(port, keys_to_del)

    @classmethod
    def filter_create_attributes(cls, port, context):
        """Filter out port attributes not required for a create."""
        cls._add_security_groups(port, context)
        cls._fixup_allowed_ipaddress_pairs(port[addr_pair.ADDRESS_PAIRS])
        cls._filter_unmapped_null(port)
        odl_utils.try_del(port, ['status'])

        # NOTE(yamahata): work around for port creation for router
        # tenant_id=''(empty string) is passed when port is created
        # by l3 plugin internally for router.
        # On the other hand, ODL doesn't accept empty string for tenant_id.
        # In that case, deduce tenant_id from network_id for now.
        # Right fix: modify Neutron so that don't allow empty string
        # for tenant_id even for port for internal use.
        # TODO(yamahata): eliminate this work around when neutron side
        # is fixed
        # assert port['tenant_id'] != ''
        if port['tenant_id'] == '':
            LOG.debug('empty string was passed for tenant_id: %s(port)', port)
            port['tenant_id'] = context._network_context._network['tenant_id']

    @classmethod
    def filter_update_attributes(cls, port, context):
        """Filter out port attributes for an update operation."""
        cls._add_security_groups(port, context)
        cls._fixup_allowed_ipaddress_pairs(port[addr_pair.ADDRESS_PAIRS])
        cls._filter_unmapped_null(port)
        odl_utils.try_del(port, ['network_id', 'id', 'status', 'tenant_id'])

    @classmethod
    def filter_create_attributes_with_plugin(cls, port, plugin, dbcontext):
        network = plugin.get_network(dbcontext, port['network_id'])
        # TODO(yamahata): port binding
        binding = {}
        context = driver_context.PortContext(
            plugin, dbcontext, port, network, binding, None)
        cls.filter_create_attributes(port, context)


class SecurityGroupFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(sg, context):
        """Filter out security-group attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(sg, context):
        """Filter out security-group attributes for an update operation."""
        pass

    @staticmethod
    def filter_create_attributes_with_plugin(sg, plugin, dbcontext):
        pass


class SecurityGroupRuleFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(sg_rule, context):
        """Filter out sg-rule attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(sg_rule, context):
        """Filter out sg-rule attributes for an update operation."""
        pass

    @staticmethod
    def filter_create_attributes_with_plugin(sg_rule, plugin, dbcontext):
        pass


class OpenDaylightDriver(object):

    """OpenDaylight Python Driver for Neutron.

    This code is the backend implementation for the OpenDaylight ML2
    MechanismDriver for OpenStack Neutron.
    """
    FILTER_MAP = {
        odl_const.ODL_NETWORKS: NetworkFilter,
        odl_const.ODL_SUBNETS: SubnetFilter,
        odl_const.ODL_PORTS: PortFilter,
        odl_const.ODL_SGS: SecurityGroupFilter,
        odl_const.ODL_SG_RULES: SecurityGroupRuleFilter,
    }
    out_of_sync = True

    def __init__(self):
        LOG.debug("Initializing OpenDaylight ML2 driver")
        self.client = odl_client.OpenDaylightRestClient.create_client()
        self.sec_handler = odl_call.OdlSecurityGroupsHandler(self)
        self.port_binding_controller = port_binding.PortBindingManager.create()
        # TODO(rzang): Each port binding controller should have any necessary
        # parameter passed in from configuration files.
        # BTW, CAP_PORT_FILTER seems being obsoleted.
        # Leave the code commmeted out for now for future reference.
        #
        # self.vif_details = {portbindings.CAP_PORT_FILTER: True}
        # self._network_topology = network_topology.NetworkTopologyManager(
        #     vif_details=self.vif_details)

    def synchronize(self, operation, object_type, context):
        """Synchronize ODL with Neutron following a configuration change."""
        if self.out_of_sync:
            self.sync_full(context._plugin)
        else:
            self.sync_single_resource(operation, object_type, context)

    def sync_resources(self, plugin, dbcontext, collection_name):
        """Sync objects from Neutron over to OpenDaylight.

        This will handle syncing networks, subnets, and ports from Neutron to
        OpenDaylight. It also filters out the requisite items which are not
        valid for create API operations.
        """
        filter_cls = self.FILTER_MAP[collection_name]
        to_be_synced = []
        obj_getter = getattr(plugin, 'get_%s' % collection_name)
        if collection_name == odl_const.ODL_SGS:
            resources = obj_getter(dbcontext, default_sg=True)
        else:
            resources = obj_getter(dbcontext)
        for resource in resources:
            try:
                # Convert underscores to dashes in the URL for ODL
                collection_name_url = collection_name.replace('_', '-')
                urlpath = collection_name_url + '/' + resource['id']
                self.client.sendjson('get', urlpath, None)
            except requests.exceptions.HTTPError as e:
                with excutils.save_and_reraise_exception() as ctx:
                    if e.response.status_code == requests.codes.not_found:
                        filter_cls.filter_create_attributes_with_plugin(
                            resource, plugin, dbcontext)
                        to_be_synced.append(resource)
                        ctx.reraise = False
            else:
                # TODO(yamahata): compare result with resource.
                # If they don't match, update it below
                pass

        if to_be_synced:
            key = collection_name[:-1] if len(to_be_synced) == 1 else (
                collection_name)
            # Convert underscores to dashes in the URL for ODL
            collection_name_url = collection_name.replace('_', '-')
            self.client.sendjson('post', collection_name_url,
                                 {key: to_be_synced})

        # https://bugs.launchpad.net/networking-odl/+bug/1371115
        # TODO(yamahata): update resources with unsyned attributes
        # TODO(yamahata): find dangling ODL resouce that was deleted in
        # neutron db

    @utils.synchronized('odl-sync-full')
    def sync_full(self, plugin):
        """Resync the entire database to ODL.

        Transition to the in-sync state on success.
        Note: we only allow a single thread in here at a time.
        """
        if not self.out_of_sync:
            return
        dbcontext = neutron_context.get_admin_context()
        for collection_name in [odl_const.ODL_NETWORKS,
                                odl_const.ODL_SUBNETS,
                                odl_const.ODL_PORTS,
                                odl_const.ODL_SGS,
                                odl_const.ODL_SG_RULES]:
            self.sync_resources(plugin, dbcontext, collection_name)
        self.out_of_sync = False

    def sync_single_resource(self, operation, object_type, context):
        """Sync over a single resource from Neutron to OpenDaylight.

        Handle syncing a single operation over to OpenDaylight, and correctly
        filter attributes out which are not required for the requisite
        operation (create or update) being handled.
        """
        # Convert underscores to dashes in the URL for ODL
        object_type_url = object_type.replace('_', '-')
        try:
            obj_id = context.current['id']
            if operation == odl_const.ODL_DELETE:
                self.out_of_sync |= not self.client.try_delete(
                    object_type_url + '/' + obj_id)
            else:
                filter_cls = self.FILTER_MAP[object_type]
                if operation == odl_const.ODL_CREATE:
                    urlpath = object_type_url
                    method = 'post'
                    attr_filter = filter_cls.filter_create_attributes
                elif operation == odl_const.ODL_UPDATE:
                    urlpath = object_type_url + '/' + obj_id
                    method = 'put'
                    attr_filter = filter_cls.filter_update_attributes
                resource = copy.deepcopy(context.current)
                attr_filter(resource, context)
                self.client.sendjson(method, urlpath,
                                     {object_type_url[:-1]: resource})
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Unable to perform %(operation)s on "
                              "%(object_type)s %(object_id)s"),
                          {'operation': operation,
                           'object_type': object_type,
                           'object_id': obj_id})
                self.out_of_sync = True

    def sync_from_callback(self, operation, object_type, res_id,
                           resource_dict):
        try:
            if operation == odl_const.ODL_DELETE:
                self.out_of_sync |= not self.client.try_delete(
                    object_type + '/' + res_id)
            else:
                if operation == odl_const.ODL_CREATE:
                    urlpath = object_type
                    method = 'post'
                elif operation == odl_const.ODL_UPDATE:
                    urlpath = object_type + '/' + res_id
                    method = 'put'
                self.client.sendjson(method, urlpath, resource_dict)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Unable to perform %(operation)s on "
                              "%(object_type)s %(res_id)s %(resource_dict)s"),
                          {'operation': operation,
                           'object_type': object_type,
                           'res_id': res_id,
                           'resource_dict': resource_dict})
                self.out_of_sync = True

    def bind_port(self, port_context):
        """Set binding for a valid segments

        """
        self.port_binding_controller.bind_port(port_context)


class OpenDaylightMechanismDriver(driver_api.MechanismDriver):

    """Mechanism Driver for OpenDaylight.

    This driver was a port from the NCS MechanismDriver.  The API
    exposed by ODL is slightly different from the API exposed by NCS,
    but the general concepts are the same.
    """

    def initialize(self):
        self.url = cfg.CONF.ml2_odl.url
        self.timeout = cfg.CONF.ml2_odl.timeout
        self.username = cfg.CONF.ml2_odl.username
        self.password = cfg.CONF.ml2_odl.password
        required_opts = ('url', 'username', 'password')
        for opt in required_opts:
            if not getattr(self, opt):
                raise cfg.RequiredOptError(opt, 'ml2_odl')

        self.odl_drv = OpenDaylightDriver()

    # Postcommit hooks are used to trigger synchronization.

    def create_network_postcommit(self, context):
        self.odl_drv.synchronize('create', odl_const.ODL_NETWORKS, context)

    def update_network_postcommit(self, context):
        self.odl_drv.synchronize('update', odl_const.ODL_NETWORKS, context)

    def delete_network_postcommit(self, context):
        self.odl_drv.synchronize('delete', odl_const.ODL_NETWORKS, context)

    def create_subnet_postcommit(self, context):
        self.odl_drv.synchronize('create', odl_const.ODL_SUBNETS, context)

    def update_subnet_postcommit(self, context):
        self.odl_drv.synchronize('update', odl_const.ODL_SUBNETS, context)

    def delete_subnet_postcommit(self, context):
        self.odl_drv.synchronize('delete', odl_const.ODL_SUBNETS, context)

    def create_port_postcommit(self, context):
        self.odl_drv.synchronize('create', odl_const.ODL_PORTS, context)

    def update_port_postcommit(self, context):
        self.odl_drv.synchronize('update', odl_const.ODL_PORTS, context)

    def delete_port_postcommit(self, context):
        self.odl_drv.synchronize('delete', odl_const.ODL_PORTS, context)

    def bind_port(self, context):
        self.odl_drv.bind_port(context)
