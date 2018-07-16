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

from neutron_lib import constants as n_const
from oslo_log import log
from oslo_serialization import jsonutils

from networking_odl.common import constants as odl_const
from networking_odl.common import utils as odl_utils


LOG = log.getLogger(__name__)


# NOTE(yamahata): As neutron keystone v3 support, tenant_id would be renamed to
# project_id. In order to keep compatibility, populate both
# 'project_id' and 'tenant_id'
# for details refer to
# https://specs.openstack.org/openstack/neutron-specs/specs/newton/moving-to-keystone-v3.html
def _populate_project_id_and_tenant_id(resource_dict):
    # NOTE(yamahata): l3 plugin passes data as dependency_list as python list
    #                 delete_router, delete_floatingip
    if not isinstance(resource_dict, dict):
        return

    project_id = resource_dict.get('project_id',
                                   resource_dict.get('tenant_id'))
    if project_id is not None:
        # NOTE(yamahata): project_id can be ""(empty string)
        resource_dict.setdefault('project_id', project_id)
        resource_dict.setdefault('tenant_id', project_id)


def _filter_unmapped_null(resource_dict, unmapped_keys):
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
    keys_to_del = [key for key in unmapped_keys
                   if resource_dict.get(key) is None]
    if keys_to_del:
        odl_utils.try_del(resource_dict, keys_to_del)


_NETWORK_UNMAPPED_KEYS = ['qos_policy_id']
_SUBNET_UNMAPPED_KEYS = ['segment_id', 'subnetpool_id']
_PORT_UNMAPPED_KEYS = ['binding:profile', 'dns_name',
                       'port_security_enabled', 'qos_policy_id']
_FIP_UNMAPPED_KEYS = ['port_id', 'fixed_ip_address', 'router_id']


def _filter_network_create(network):
    odl_utils.try_del(network, ['status', 'subnets'])
    _filter_unmapped_null(network, _NETWORK_UNMAPPED_KEYS)


def _filter_network_update(network):
    odl_utils.try_del(network, ['id', 'status', 'subnets',
                                'tenant_id', 'project_id'])
    _filter_unmapped_null(network, _NETWORK_UNMAPPED_KEYS)


def _filter_floatingip(fip):
    _filter_unmapped_null(fip, _FIP_UNMAPPED_KEYS)


def _filter_subnet_create(subnet):
    _filter_unmapped_null(subnet, _SUBNET_UNMAPPED_KEYS)


def _filter_subnet_update(subnet):
    odl_utils.try_del(subnet, ['id', 'network_id', 'ip_version', 'cidr',
                               'tenant_id', 'project_id'])
    _filter_unmapped_null(subnet, _SUBNET_UNMAPPED_KEYS)


def _convert_value_to_str(dictionary, key):
    try:
        # use jsonutils to convert unicode & ascii
        dictionary[key] = jsonutils.dumps(dictionary[key])
    except KeyError:
        LOG.warning("key %s is not present in dict %s", key, dictionary)


def _filter_port(port, attributes):
    odl_utils.try_del(port, attributes)
    _filter_unmapped_null(port, _PORT_UNMAPPED_KEYS)
    # ODL excpects binding:profile to be a string, not a dict
    _convert_value_to_str(port, key='binding:profile')


def _filter_port_create(port):
    """Filter out port attributes not required for a create."""
    _filter_port(port, ['status'])


def _filter_port_update(port):
    """Filter out port attributes for an update operation."""
    _filter_port(port, ['network_id', 'id', 'status', 'tenant_id',
                        'project_id'])


def _filter_router_update(router):
    """Filter out attributes for an update operation."""
    odl_utils.try_del(router, ['id', 'tenant_id', 'project_id', 'status'])


# neutron has multiple ICMPv6 names
# https://bugs.launchpad.net/tempest/+bug/1671366
# REVISIT(yamahata): once neutron upstream is fixed to store unified form,
#                    this can be removed.
_ICMPv6_NAMES = (
    n_const.PROTO_NAME_ICMP,
    n_const.PROTO_NAME_IPV6_ICMP,
    n_const.PROTO_NAME_IPV6_ICMP_LEGACY,
)


def _sgrule_scrub_icmpv6_name(sgrule):
    if (sgrule.get('ethertype') == n_const.IPv6 and
            sgrule.get('protocol') in _ICMPv6_NAMES):
        sgrule['protocol'] = n_const.PROTO_NAME_IPV6_ICMP_LEGACY


# ODL neturon northbound knows the following protocol names.
# It's safe to pass those names
_ODL_KNOWN_PROTOCOL_NAMES = (
    n_const.PROTO_NAME_TCP,
    n_const.PROTO_NAME_UDP,
    n_const.PROTO_NAME_ICMP,
    n_const.PROTO_NAME_IPV6_ICMP_LEGACY,
)


def _sgrule_scrub_unknown_protocol_name(protocol):
    """Convert unknown protocol name to actual interger.

    OpenDaylight does't want to keep catching up list of protocol names.
    So networking-odl converts unknown protcol name into integer
    """
    if protocol in _ODL_KNOWN_PROTOCOL_NAMES:
        return protocol
    if protocol in n_const.IP_PROTOCOL_MAP:
        return n_const.IP_PROTOCOL_MAP[protocol]
    return protocol


def _filter_security_group_rule(sg_rule):
    _sgrule_scrub_icmpv6_name(sg_rule)
    if sg_rule.get('protocol'):
        sg_rule['protocol'] = _sgrule_scrub_unknown_protocol_name(
            sg_rule['protocol'])


_FILTER_MAP = {
    (odl_const.ODL_NETWORK, odl_const.ODL_CREATE): _filter_network_create,
    (odl_const.ODL_NETWORK, odl_const.ODL_UPDATE): _filter_network_update,
    (odl_const.ODL_SUBNET, odl_const.ODL_CREATE): _filter_subnet_create,
    (odl_const.ODL_SUBNET, odl_const.ODL_UPDATE): _filter_subnet_update,
    (odl_const.ODL_PORT, odl_const.ODL_CREATE): _filter_port_create,
    (odl_const.ODL_PORT, odl_const.ODL_UPDATE): _filter_port_update,
    (odl_const.ODL_ROUTER, odl_const.ODL_UPDATE): _filter_router_update,
    (odl_const.ODL_SG_RULE, odl_const.ODL_CREATE): _filter_security_group_rule,
    (odl_const.ODL_SG_RULE, odl_const.ODL_UPDATE): _filter_security_group_rule,
    (odl_const.ODL_FLOATINGIP, odl_const.ODL_UPDATE): _filter_floatingip,
}


def filter_for_odl(object_type, operation, data):
    """Filter out the attributed before sending the data to ODL"""
    filter_key = (object_type, operation)
    if filter_key in _FILTER_MAP:
        _FILTER_MAP[filter_key](data)
    _populate_project_id_and_tenant_id(data)
