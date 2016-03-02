# Copyright (c) 2015 Intel Inc.
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

from copy import deepcopy
import requests
import six

from oslo_log import log as logging
from oslo_serialization import jsonutils

from networking_odl.common import client
from networking_odl.common import constants as odl_const


LOG = logging.getLogger(__name__)

OK = requests.codes.ok
NO_CONTENT = requests.codes.no_content
NOT_ALLOWED = requests.codes.not_allowed
NOT_FOUND = requests.codes.not_found
BAD_REQUEST = requests.codes.bad_request


class OpenDaylightLwtClient(client.OpenDaylightRestClient):
    """Lightweight testing client"""

    lwt_dict = {odl_const.ODL_NETWORKS: {},
                odl_const.ODL_SUBNETS: {},
                odl_const.ODL_PORTS: {},
                odl_const.ODL_SGS: {},
                odl_const.ODL_SG_RULES: {},
                odl_const.ODL_LOADBALANCERS: {},
                odl_const.ODL_LISTENERS: {},
                odl_const.ODL_POOLS: {},
                odl_const.ODL_MEMBERS: {},
                odl_const.ODL_HEALTHMONITORS: {}}

    @classmethod
    def _make_response(cls, status_code=OK, content=None):
        """Only supports 'content-type': 'application/json'"""
        response = requests.models.Response()
        response.status_code = status_code
        if content:
            response.raw = six.BytesIO(
                jsonutils.dumps(content).encode('utf-8'))

        return response

    @classmethod
    def _get_resource_id(cls, urlpath):
        # resouce ID is the last element of urlpath
        return str(urlpath).rsplit('/', 1)[-1]

    @classmethod
    def post(cls, resource_type, resource_dict, urlpath, resource_list):
        """No ID in URL, elements in resource_list must have ID"""

        if resource_list is None:
            raise ValueError("resource_list can not be None")

        for resource in resource_list:
            if resource['id'] in resource_dict:
                LOG.debug("%s %s already exists", resource_type,
                          resource['id'])
                response = cls._make_response(NOT_ALLOWED)
                raise requests.exceptions.HTTPError(response=response)

            resource_dict[resource['id']] = deepcopy(resource)

        return cls._make_response(NO_CONTENT)

    @classmethod
    def put(cls, resource_type, resource_dict, urlpath, resource_list):

        resource_id = cls._get_resource_id(urlpath)

        if resource_list is None:
            raise ValueError("resource_list can not be None")

        if resource_id and len(resource_list) != 1:
            LOG.debug("Updating %s with multiple resources", urlpath)
            response = cls._make_response(BAD_REQUEST)
            raise requests.exceptions.HTTPError(response=response)

        for resource in resource_list:
            res_id = resource_id or resource['id']
            if res_id in resource_dict:
                resource_dict[res_id].update(deepcopy(resource))
            else:
                LOG.debug("%s %s does not exist", resource_type, res_id)
                response = cls._make_response(NOT_FOUND)
                raise requests.exceptions.HTTPError(response=response)

        return cls._make_response(NO_CONTENT)

    @classmethod
    def delete(cls, resource_type, resource_dict, urlpath, resource_list):

        if resource_list is None:
            resource_id = cls._get_resource_id(urlpath)
            id_list = [resource_id]
        else:
            id_list = [res['id'] for res in resource_list]

        for res_id in id_list:
            removed = resource_dict.pop(res_id, None)
            if removed is None:
                LOG.debug("%s %s does not exist", resource_type, res_id)
                response = cls._make_response(NOT_FOUND)
                raise requests.exceptions.HTTPError(response=response)

        return cls._make_response(NO_CONTENT)

    @classmethod
    def get(cls, resource_type, resource_dict, urlpath, resource_list=None):

        resource_id = cls._get_resource_id(urlpath)

        if resource_id:
            resource = resource_dict.get(resource_id)
            if resource is None:
                LOG.debug("%s %s does not exist", resource_type, resource_id)
                response = cls._make_response(NOT_FOUND)
                raise requests.exceptions.HTTPError(response=response)
            else:
                # When getting single resource, return value is a dict
                r_list = {resource_type[:-1]: deepcopy(resource)}
                return cls._make_response(OK, r_list)

        r_list = [{resource_type[:-1]: deepcopy(res)}
                  for res in six.itervalues(resource_dict)]

        return cls._make_response(OK, r_list)

    def sendjson(self, method, urlpath, obj=None):
        """Lightweight testing without ODL"""

        if '/' not in urlpath:
            urlpath += '/'

        resource_type = str(urlpath).split('/', 1)[0]
        resource_type = resource_type.replace('-', '_')

        resource_dict = self.lwt_dict.get(resource_type)

        if resource_dict is None:
            LOG.debug("Resource type %s is not supported", resource_type)
            response = self._make_response(NOT_FOUND)
            raise requests.exceptions.HTTPError(response=response)

        func = getattr(self, str(method).lower())

        resource_list = None
        if obj:
            """If obj is not None, it can only have one entry"""
            assert len(obj) == 1, "Obj can only have one entry"

            key, resource_list = list(obj.items())[0]

            if not isinstance(resource_list, list):
                # Need to transform resource_list to a real list, i.e. [res]
                resource_list = [resource_list]

        return func(resource_type, resource_dict, urlpath, resource_list)
