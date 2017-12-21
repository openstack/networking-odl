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
from oslo_utils import excutils

from neutron.db import api as db_api

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

LOG_TEMPLATE = ("(%(msg)s) with ODL_OPS (%(op)s) ODL_RES_TYPE (%(res_type)s) "
                "ODL_RES_ID (%(res_id)s)) ODL_RES_DICT (%(res_dict)s) "
                "DATA (%(data)s)")


def _log_on_callback(lvl, msg, op, res_type, res_id, res_dict, data):
    LOG.log(lvl, LOG_TEMPLATE,
            {'msg': msg, 'op': op, 'res_type': res_type, 'res_id': res_id,
             'res_dict': res_dict, 'data': data,
             'exc_info': True if lvl >= logging.ERROR else False})


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
        if 'payload' in kwargs:
            # TODO(boden): remove shim once all callbacks use payloads
            context = kwargs['payload'].context
            res = kwargs['payload'].desired_state
            res_id = kwargs['payload'].resource_id
            copy_kwargs = kwargs
        else:
            context = kwargs['context']
            res = kwargs.get(resource)
            res_id = kwargs.get("%s_id" % resource)
            copy_kwargs = kwargs.copy()
            copy_kwargs.pop('context')

        if res_id is None:
            res_id = res.get('id')
        odl_res_type = _RESOURCE_MAPPING[resource]

        odl_ops = _OPERATION_MAPPING[event]
        odl_res_dict = None if res is None else {odl_res_type.singular: res}

        _log_on_callback(logging.DEBUG, "Calling callback", odl_ops,
                         odl_res_type, res_id, odl_res_dict, copy_kwargs)
        try:
            callback(context, odl_ops, odl_res_type, res_id, odl_res_dict,
                     **copy_kwargs)
        except Exception as e:
            # In case of precommit, neutron registry notification caller
            # doesn't log its exception. In networking-odl case, we don't
            # normally throw exception. So log it here for debug
            with excutils.save_and_reraise_exception():
                if not db_api.is_retriable(e):
                    _log_on_callback(logging.ERROR, "Exception from callback",
                                     odl_ops, odl_res_type, res_id,
                                     odl_res_dict, copy_kwargs)

    def sg_callback_precommit(self, resource, event, trigger, **kwargs):
        self._sg_callback(self._precommit, resource, event, trigger, **kwargs)

    def sg_callback_postcommit(self, resource, event, trigger, **kwargs):
        self._sg_callback(self._postcommit, resource, event, trigger, **kwargs)
