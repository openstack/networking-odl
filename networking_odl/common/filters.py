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
import abc
import six

from networking_odl.common import constants as odl_const
from networking_odl.common import utils as odl_utils


@six.add_metaclass(abc.ABCMeta)
class ResourceFilterBase(object):
    @staticmethod
    @abc.abstractmethod
    def filter_create_attributes(resource):
        pass

    @staticmethod
    @abc.abstractmethod
    def filter_update_attributes(resource):
        pass


class NetworkFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(network):
        """Filter out network attributes not required for a create."""
        odl_utils.try_del(network, ['status', 'subnets'])

    @staticmethod
    def filter_update_attributes(network):
        """Filter out network attributes for an update operation."""
        odl_utils.try_del(network, ['id', 'status', 'subnets', 'tenant_id'])


class SubnetFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(subnet):
        """Filter out subnet attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(subnet):
        """Filter out subnet attributes for an update operation."""
        odl_utils.try_del(subnet, ['id', 'network_id', 'ip_version', 'cidr',
                          'allocation_pools', 'tenant_id'])


class PortFilter(ResourceFilterBase):
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
    def filter_create_attributes(cls, port):
        """Filter out port attributes not required for a create."""
        cls._filter_unmapped_null(port)
        odl_utils.try_del(port, ['status'])

    @classmethod
    def filter_update_attributes(cls, port):
        """Filter out port attributes for an update operation."""
        cls._filter_unmapped_null(port)
        odl_utils.try_del(port, ['network_id', 'id', 'status', 'mac_address',
                          'tenant_id', 'fixed_ips'])


class SecurityGroupFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(sg):
        """Filter out security-group attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(sg):
        """Filter out security-group attributes for an update operation."""
        pass


class SecurityGroupRuleFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(sg_rule):
        """Filter out sg-rule attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(sg_rule):
        """Filter out sg-rule attributes for an update operation."""
        pass


class RouterFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(router):
        """Filter out attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(router):
        """Filter out attributes for an update operation."""
        odl_utils.try_del(router, ['id', 'tenant_id', 'status'])


class FloatingIPFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(floatingip):
        """Filter out attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(floatingip):
        """Filter out attributes for an update operation."""
        pass


class RouterIntfFilter(ResourceFilterBase):
    @staticmethod
    def filter_add_attributes(routerintf):
        """Filter out attributes not required for a create."""
        pass

    @staticmethod
    def filter_remove_attributes(routerintf):
        """Filter out attributes for an update operation."""
        pass

FILTER_MAP = {
    odl_const.ODL_NETWORK: NetworkFilter,
    odl_const.ODL_SUBNET: SubnetFilter,
    odl_const.ODL_PORT: PortFilter,
    odl_const.ODL_ROUTER: RouterFilter,
    odl_const.ODL_ROUTER_INTF: RouterIntfFilter,
    odl_const.ODL_FLOATINGIP: FloatingIPFilter,
    odl_const.ODL_SG: SecurityGroupFilter,
    odl_const.ODL_SG_RULE: SecurityGroupRuleFilter,
}
