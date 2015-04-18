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


def sg_callback(resource, event, trigger, **kwargs):
    from networking_odl.ml2 import mech_driver

    if resource == resources.SECURITY_GROUP:
        odl_resource = odl_const.ODL_SGS
        res = kwargs.get('security_group')
        res_id = res['id']
        if event == events.AFTER_CREATE:
            oper = 'create'
        elif event == events.AFTER_UPDATE:
            oper = 'update'
        elif event == events.AFTER_DELETE:
            oper = 'delete'
    elif resource == resources.SECURITY_GROUP_RULE:
        odl_resource = odl_const.ODL_SG_RULES
        res = kwargs.get('security_group_rule')
        res_id = res['id']
        if event == events.AFTER_CREATE:
            oper = 'create'
        elif event == events.AFTER_UPDATE:
            oper = 'update'
        elif event == events.AFTER_DELETE:
            oper = 'delete'

    odl_drv = mech_driver.OpenDaylightDriver()
    # NOTE(mestery): We have to set out_of_sync to False to prevent syncing
    # the entire neutron DB over to ODL.
    odl_drv.out_of_sync = False
    odl_drv.sync_from_callback(oper, odl_resource, res_id, res)


def subscribe():
    registry.subscribe(
        sg_callback, resources.SECURITY_GROUP, events.AFTER_CREATE)
    registry.subscribe(
        sg_callback, resources.SECURITY_GROUP, events.AFTER_UPDATE)
    registry.subscribe(
        sg_callback, resources.SECURITY_GROUP, events.AFTER_DELETE)
    registry.subscribe(
        sg_callback, resources.SECURITY_GROUP_RULE, events.AFTER_CREATE)
    registry.subscribe(
        sg_callback, resources.SECURITY_GROUP_RULE, events.AFTER_DELETE)
