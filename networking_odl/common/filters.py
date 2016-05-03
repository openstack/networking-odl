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
from networking_odl.common import utils as odl_utils


def _filter_network_create(network):
    odl_utils.try_del(network, ['status', 'subnets'])


def _filter_network_update(network):
    odl_utils.try_del(network, ['id', 'status', 'subnets', 'tenant_id'])


def _filter_subnet_update(subnet):
    odl_utils.try_del(subnet, ['id', 'network_id', 'ip_version', 'cidr',
                      'allocation_pools', 'tenant_id'])


def _filter_port_unmapped_null(port):
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


def _filter_port_create(port):
    """Filter out port attributes not required for a create."""
    _filter_port_unmapped_null(port)
    odl_utils.try_del(port, ['status'])


def _filter_port_update(port):
    """Filter out port attributes for an update operation."""
    _filter_port_unmapped_null(port)
    odl_utils.try_del(port, ['network_id', 'id', 'status', 'mac_address',
                      'tenant_id', 'fixed_ips'])


def _filter_router_update(router):
    """Filter out attributes for an update operation."""
    odl_utils.try_del(router, ['id', 'tenant_id', 'status'])


_FILTER_MAP = {
    (odl_const.ODL_NETWORK, odl_const.ODL_CREATE): _filter_network_create,
    (odl_const.ODL_NETWORK, odl_const.ODL_UPDATE): _filter_network_update,
    (odl_const.ODL_SUBNET, odl_const.ODL_UPDATE): _filter_subnet_update,
    (odl_const.ODL_PORT, odl_const.ODL_CREATE): _filter_port_create,
    (odl_const.ODL_PORT, odl_const.ODL_UPDATE): _filter_port_update,
    (odl_const.ODL_ROUTER, odl_const.ODL_UPDATE): _filter_router_update,
}


def filter_for_odl(object_type, operation, data):
    """Filter out the attributed before sending the data to ODL"""
    filter_key = (object_type, operation)
    if filter_key in _FILTER_MAP:
        _FILTER_MAP[filter_key](data)
