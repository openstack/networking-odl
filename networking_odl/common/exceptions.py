# Copyright (c) 2017 NEC Corp
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

from neutron_lib import exceptions

from neutron._i18n import _


class NetworkingODLException(exceptions.NeutronException):
    """Base Networking-ODL exception."""
    pass


class FullSyncError(NetworkingODLException):
    """Base exception for Full Sync"""
    pass


class UnsupportedResourceType(NetworkingODLException):
    """An exception for unsupported resource for full sync and recovery"""
    message = _("unsupported resource type: %(resource)s")


class PluginMethodNotFound(NetworkingODLException, AttributeError):
    """An exception indicating plugin method was not found.

       Specialization of AttributeError and NetworkingODLException indicating
       requested plugin method could not be found.

       :param method: Name of the method being accessed.
       :param plugin: Plugin name expected to have required method.
    """
    message = _("%(method)s not found in %(plugin)s")


class ResourceNotRegistered(FullSyncError):
    """An exception indicating resource is not registered for maintenance task.

       Specialization of FullSync error indicating resource is not registered
       for maintenance tasks full sync and recovery.

       :param resource_type: Resource type not registered for maintenance task.
    """
    message = _("%(resource_type)s resource is not registered for maintenance")
