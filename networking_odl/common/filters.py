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
    @classmethod
    def filter_create_attributes(cls, port):
        """Filter out port attributes not required for a create."""
        # TODO(kmestery): Converting to uppercase due to ODL bug
        # https://bugs.opendaylight.org/show_bug.cgi?id=477
        port['mac_address'] = port['mac_address'].upper()
        odl_utils.try_del(port, ['status'])

    @classmethod
    def filter_update_attributes(cls, port):
        """Filter out port attributes for an update operation."""
        odl_utils.try_del(port, ['network_id', 'id', 'status', 'mac_address',
                          'tenant_id', 'fixed_ips'])


class SecurityGroupFilter(ResourceFilterBase):
    @staticmethod
    def filter_create_attributes(sg, context):
        """Filter out security-group attributes not required for a create."""
        pass

    @staticmethod
    def filter_update_attributes(sg, context):
        """Filter out security-group attributes for an update operation."""
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

FILTER_MAP = {
    odl_const.ODL_NETWORK: NetworkFilter,
    odl_const.ODL_SUBNET: SubnetFilter,
    odl_const.ODL_PORT: PortFilter,
}
