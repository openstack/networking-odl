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

from neutron_lib.plugins import directory
from oslo_log import log as logging

from networking_odl.common import exceptions

LOG = logging.getLogger(__name__)

ALL_RESOURCES = {}


def get_driver(resource_type):
    try:
        return ALL_RESOURCES[resource_type]
    except KeyError:
        raise exceptions.ResourceNotRegistered(resource_type=resource_type)


class ResourceBaseDriver(object):
    """Base class for all the drivers to support full sync

       ResourceBaseDriver class acts as base class for all the drivers and
       provides default behaviour for full sync functionality.

       A driver has to provide class or object attribute RESOURCES, specifying
       resources it manages. RESOURCES must be a dictionary, keys of the
       dictionary should be resource type and value should be method suffix
       or plural used for the resources.

       A driver has to provide plugin type for itself, as class or object
       attribute. Its value should be the same, as used by neutron to
       register plugin for the resources it manages.
    """

    RESOURCES = {}
    plugin_type = None

    def __init__(self, *args, **kwargs):
        super(ResourceBaseDriver, self).__init__(*args, **kwargs)
        for resource in self.RESOURCES:
            ALL_RESOURCES[resource] = self

    def _get_resource_getter(self, method_suffix):
        method_name = "get_%s" % method_suffix
        try:
            return getattr(self.plugin, method_name)
        except AttributeError:
            raise exceptions.PluginMethodNotFound(plugin=self.plugin_type,
                                                  method=method_name)

    def get_resources_for_full_sync(self, context, resource_type):
        """Provide all resources of type resource_type """
        if resource_type not in self.RESOURCES:
            raise exceptions.UnsupportedResourceType

        resource_getter = self._get_resource_getter(
            self.RESOURCES[resource_type])

        return resource_getter(context)

    @property
    def plugin(self):
        return directory.get_plugin(self.plugin_type)

    def get_resource_for_recovery(self, context, obj):
        resource_getter = self._get_resource_getter(obj.object_type)
        return resource_getter(context, obj.object_uuid)
