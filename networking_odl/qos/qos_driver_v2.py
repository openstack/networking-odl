# Copyright (c) 2016 OpenStack Foundation
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
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from networking_odl.common import config as odl_conf
from networking_odl.common import constants as odl_const
from networking_odl.journal import journal
from networking_odl.qos import qos_utils
from neutron.services.qos.notification_drivers import qos_base

LOG = logging.getLogger(__name__)


class OpenDaylightQosDriver(qos_base.QosServiceNotificationDriverBase):

    """OpenDaylight QOS Driver

    This code is backend implementation for Opendaylight Qos
    driver for Openstack Neutron.
    """

    def __init__(self):
        LOG.debug("Initializing OpenDaylight Qos driver")
        cfg.CONF.register_opts(odl_conf.odl_opts, "ml2_odl")
        self.journal = journal.OpendaylightJournalThread()

    def get_description(self):
        """Returns string description of driver"""
        return "QoS ODL driver"

    # TODO(manjeets) QoS interface does not have precommit
    # and postcommit mechanism for now, Revisit this driver
    # once interface is fixed and separate record in journal
    # and sync event to precommit and postcommit.
    # https://review.openstack.org/#/c/421818/

    @log_helpers.log_method_call
    def create_policy(self, context, qos_policy):
        data = qos_utils.convert_rules_format(qos_policy.to_dict())
        journal.record(context, context,
                       odl_const.ODL_QOS_POLICY, data['id'],
                       odl_const.ODL_CREATE, data)
        self.journal.set_sync_event()

    @log_helpers.log_method_call
    def update_policy(self, context, qos_policy):
        data = qos_utils.convert_rules_format(qos_policy.to_dict())
        journal.record(context, context,
                       odl_const.ODL_QOS_POLICY, data['id'],
                       odl_const.ODL_UPDATE, data)
        self.journal.set_sync_event()

    @log_helpers.log_method_call
    def delete_policy(self, context, qos_policy):
        data = qos_utils.convert_rules_format(qos_policy.to_dict())
        journal.record(context, context,
                       odl_const.ODL_QOS_POLICY, data['id'],
                       odl_const.ODL_DELETE, data)
        self.journal.set_sync_event()
