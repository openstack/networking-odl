# Copyright (c) 2016 OpenStack Foundation
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

from neutron.services.qos.notification_drivers import qos_base

from networking_odl.common import client as odl_client
from networking_odl.common import constants as odl_const
from networking_odl.common import utils
from networking_odl.qos import qos_utils


LOG = logging.getLogger(__name__)


class OpenDaylightQosDriver(qos_base.QosServiceNotificationDriverBase):
    """OpenDaylight Python Driver for Neutron.

    This code is the backend implementation for the OpenDaylight QoS
    NotifcationDriver for OpenStack Neutron.
    """

    def __init__(self):
        LOG.debug("Initializing OpenDaylight QoS driver")
        self.client = odl_client.OpenDaylightRestClient.create_client()

    def send_resource(self, operation, object_type, data):
        """Send over a single resource from Neutron to OpenDaylight.

        Prepare a rest call and send a single resource to ODL NB
        """
        # Convert underscores to dashes in the URL for ODL
        object_type_url = utils.neutronify(object_type)
        obj_id = data['id']
        if operation == odl_const.ODL_DELETE:
            self.client.try_delete(object_type_url + '/' + obj_id)
        else:
            if operation == odl_const.ODL_CREATE:
                urlpath = object_type_url
                method = 'post'
            elif operation == odl_const.ODL_UPDATE:
                urlpath = object_type_url + '/' + obj_id
                method = 'put'
            policy_data = qos_utils.convert_rules_format(data)
            self.client.sendjson(method, urlpath,
                                 {odl_const.ODL_QOS_POLICY: policy_data})

    def get_description(self):
        pass

    def create_policy(self, context, qos_policy):
        data = qos_policy.to_dict()
        self.send_resource(odl_const.ODL_CREATE,
                           odl_const.ODL_QOS_POLICIES,
                           data)

    def delete_policy(self, context, qos_policy):
        data = qos_policy.to_dict()
        self.send_resource(odl_const.ODL_DELETE,
                           odl_const.ODL_QOS_POLICIES,
                           data)

    def update_policy(self, context, qos_policy):
        data = qos_policy.to_dict()
        self.send_resource(odl_const.ODL_UPDATE,
                           odl_const.ODL_QOS_POLICIES,
                           data)
