# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
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

from oslo_log import log as logging

from neutron.callbacks import events
from neutron.callbacks import registry
from neutron.callbacks import resources

from networking_odl.common import constants as odl_const

LOG = logging.getLogger(__name__)


class OdlSecurityGroupsHandler(object):

    def __init__(self, odl_client, event_type="AFTER"):
        self.odl_client = odl_client
        self.subscribe(event_type)

    def sg_callback(self, resource, event, trigger, **kwargs):

        res_key_mapping = {
            odl_const.ODL_SGS: odl_const.ODL_SG,
            odl_const.ODL_SG_RULES: odl_const.ODL_SG_RULE,
        }
        res_name_mapping = {
            resources.SECURITY_GROUP: odl_const.ODL_SGS,
            resources.SECURITY_GROUP_RULE: odl_const.ODL_SG_RULES,
        }
        ops_mapping = {
            events.AFTER_CREATE: odl_const.ODL_CREATE,
            events.AFTER_UPDATE: odl_const.ODL_UPDATE,
            events.AFTER_DELETE: odl_const.ODL_DELETE,
            events.PRECOMMIT_CREATE: odl_const.ODL_CREATE,
            events.PRECOMMIT_UPDATE: odl_const.ODL_UPDATE,
            events.PRECOMMIT_DELETE: odl_const.ODL_DELETE,
        }

        # Loop up the ODL's counterpart resource label
        # e.g. resources.SECURITY_GROUP -> odl_const.ODL_SGS
        # Note: 1) url will use dashes instead of underscore;
        #       2) when res is a list, append 's' to odl_res_key
        # Ref: https://github.com/opendaylight/neutron/blob/master
        #      /northbound-api/src/main/java/org/opendaylight
        #      /neutron/northbound/api
        #      /NeutronSecurityGroupRequest.java#L33
        res = kwargs.get(resource)
        res_id = kwargs.get("%s_id" % resource)
        odl_res_type = res_name_mapping[resource]
        odl_res_key = res_key_mapping[odl_res_type]
        odl_ops = ops_mapping[event]
        odl_res_type_uri = odl_res_type.replace('_', '-')

        if type(res) is list:
            odl_res_key += "s"

        if res is None:
            odl_res_dict = None
        else:
            odl_res_dict = {odl_res_key: res}

        LOG.debug("Calling sync_from_callback with ODL_OPS (%(odl_ops)s) "
                  "ODL_RES_TYPE (%(odl_res_type)s) RES_ID (%(res_id)s) "
                  "ODL_RES_KEY (%(odl_res_key)s) RES (%(res)s) "
                  "KWARGS (%(kwargs)s)",
                  {'odl_ops': odl_ops, 'odl_res_type': odl_res_type,
                   'res_id': res_id, 'odl_res_key': odl_res_key, 'res': res,
                   'kwargs': kwargs})

        self.odl_client.sync_from_callback(odl_ops, odl_res_type_uri, res_id,
                                           odl_res_dict)

    def subscribe(self, event_type):
        registry.subscribe(
            self.sg_callback, resources.SECURITY_GROUP,
            getattr(events, "%s_CREATE" % event_type))
        registry.subscribe(
            self.sg_callback, resources.SECURITY_GROUP,
            getattr(events, "%s_UPDATE" % event_type))
        registry.subscribe(
            self.sg_callback, resources.SECURITY_GROUP,
            getattr(events, "%s_DELETE" % event_type))
        registry.subscribe(
            self.sg_callback, resources.SECURITY_GROUP_RULE,
            getattr(events, "%s_CREATE" % event_type))
        registry.subscribe(
            self.sg_callback, resources.SECURITY_GROUP_RULE,
            getattr(events, "%s_DELETE" % event_type))
