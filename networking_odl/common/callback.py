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

import collections

from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from oslo_log import log as logging

from networking_odl.common import constants as odl_const

LOG = logging.getLogger(__name__)

ODLResource = collections.namedtuple('ODLResource', ('singular', 'plural'))
_RESOURCE_MAPPING = {
    resources.SECURITY_GROUP: ODLResource(odl_const.ODL_SG, odl_const.ODL_SGS),
    resources.SECURITY_GROUP_RULE: ODLResource(odl_const.ODL_SG_RULE,
                                               odl_const.ODL_SG_RULES),
}
_OPERATION_MAPPING = {
    events.PRECOMMIT_CREATE: odl_const.ODL_CREATE,
    events.PRECOMMIT_UPDATE: odl_const.ODL_UPDATE,
    events.PRECOMMIT_DELETE: odl_const.ODL_DELETE,
    events.AFTER_CREATE: odl_const.ODL_CREATE,
    events.AFTER_UPDATE: odl_const.ODL_UPDATE,
    events.AFTER_DELETE: odl_const.ODL_DELETE,
}


class OdlSecurityGroupsHandler(object):

    def __init__(self, precommit, postcommit):
        assert postcommit is not None
        self._precommit = precommit
        self._postcommit = postcommit
        self._subscribe()

    def _subscribe(self):
        if self._precommit is not None:
            for event in (events.PRECOMMIT_CREATE, events.PRECOMMIT_DELETE):
                registry.subscribe(self.sg_callback_precommit,
                                   resources.SECURITY_GROUP, event)
                registry.subscribe(self.sg_callback_precommit,
                                   resources.SECURITY_GROUP_RULE, event)
            registry.subscribe(
                self.sg_callback_precommit, resources.SECURITY_GROUP,
                events.PRECOMMIT_UPDATE)

        for event in (events.AFTER_CREATE, events.AFTER_DELETE):
            registry.subscribe(self.sg_callback_postcommit,
                               resources.SECURITY_GROUP, event)
            registry.subscribe(self.sg_callback_postcommit,
                               resources.SECURITY_GROUP_RULE, event)

        registry.subscribe(self.sg_callback_postcommit,
                           resources.SECURITY_GROUP, events.AFTER_UPDATE)

    def _sg_callback(self, callback, resource, event, trigger, **kwargs):
        context = kwargs['context']
        res = kwargs.get(resource)
        res_id = kwargs.get("%s_id" % resource)
        if res_id is None:
            res_id = res.get('id')
        odl_res_type = _RESOURCE_MAPPING[resource]

        odl_ops = _OPERATION_MAPPING[event]
        odl_res_dict = None if res is None else {odl_res_type.singular: res}

        LOG.debug("Calling sync_from_callback with ODL_OPS (%(odl_ops)s) "
                  "ODL_RES_TYPE (%(odl_res_type)s) RES_ID (%(res_id)s) "
                  "ODL_RES_DICT (%(odl_res_dict)s) KWARGS (%(kwargs)s)",
                  {'odl_ops': odl_ops, 'odl_res_type': odl_res_type,
                   'res_id': res_id, 'odl_res_dict': odl_res_dict,
                   'kwargs': kwargs})

        copy_kwargs = kwargs.copy()
        copy_kwargs.pop('context')
        callback(context, odl_ops, odl_res_type, res_id, odl_res_dict,
                 **copy_kwargs)

    def sg_callback_precommit(self, resource, event, trigger, **kwargs):
        self._sg_callback(self._precommit, resource, event, trigger, **kwargs)

    def sg_callback_postcommit(self, resource, event, trigger, **kwargs):
        self._sg_callback(self._postcommit, resource, event, trigger, **kwargs)
