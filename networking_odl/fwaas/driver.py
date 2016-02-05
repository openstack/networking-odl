#
# Copyright (C) 2013 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#

from oslo_log import log as logging

from neutron_fwaas.services.firewall.drivers import fwaas_base

from networking_odl.common import client as odl_client
from networking_odl.common import config  # noqa

LOG = logging.getLogger(__name__)


class OpenDaylightFwaasDriver(fwaas_base.FwaasDriverBase):

    """OpenDaylight FWaaS Driver

    This code is the backend implementation for the OpenDaylight FWaaS
    driver for OpenStack Neutron.
    """

    def __init__(self):
        LOG.debug("Initializing OpenDaylight FWaaS driver")
        self.client = odl_client.OpenDaylightRestClient.create_client()

    def create_firewall(self, apply_list, firewall):
        """Create the Firewall with default (drop all) policy.

        The default policy will be applied on all the interfaces of
        trusted zone.
        """
        pass

    def delete_firewall(self, apply_list, firewall):
        """Delete firewall.

        Removes all policies created by this instance and frees up
        all the resources.
        """
        pass

    def update_firewall(self, apply_list, firewall):
        """Apply the policy on all trusted interfaces.

        Remove previous policy and apply the new policy on all trusted
        interfaces.
        """
        pass

    def apply_default_policy(self, apply_list, firewall):
        """Apply the default policy on all trusted interfaces.

        Remove current policy and apply the default policy on all trusted
        interfaces.
        """
        pass
