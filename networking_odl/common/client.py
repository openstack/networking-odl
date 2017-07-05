# Copyright (c) 2014 Red Hat Inc.
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

import threading

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import excutils
import requests
from requests import sessions

from networking_odl.common import constants as odl_const
from networking_odl.common import utils

LOG = log.getLogger(__name__)
cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')


class OpenDaylightRestClient(object):
    @staticmethod
    def _check_opt(url):
        if not url:
            raise cfg.RequiredOptError('url', cfg.OptGroup('ml2_odl'))
        required_opts = ('url', 'username', 'password')
        for opt in required_opts:
            if not getattr(cfg.CONF.ml2_odl, opt):
                raise cfg.RequiredOptError(opt, cfg.OptGroup('ml2_odl'))

    @classmethod
    def create_client(cls, url=None):
        if cfg.CONF.ml2_odl.enable_lightweight_testing:
            LOG.debug("ODL lightweight testing is enabled, "
                      "returning a OpenDaylightLwtClient instance")

            # Have to import at here, otherwise we create a dependency loop
            from networking_odl.common import lightweight_testing as lwt
            cls = lwt.OpenDaylightLwtClient

        url = url or cfg.CONF.ml2_odl.url
        cls._check_opt(url)
        return cls(
            url,
            cfg.CONF.ml2_odl.username,
            cfg.CONF.ml2_odl.password,
            cfg.CONF.ml2_odl.timeout)

    def __init__(self, url, username, password, timeout):
        super(OpenDaylightRestClient, self).__init__()
        self.url = url
        self.timeout = timeout
        self.session = sessions.Session()
        self.session.auth = (username, password)

    def get_resource(self, resource_type, resource_id):
        response = self.get(utils.make_url_object(resource_type) + '/' +
                            resource_id)
        if response.status_code == requests.codes.not_found:
            return None

        return self._check_response(response).json()

    def get(self, urlpath='', data=None):
        return self.request('get', urlpath, data)

    def put(self, urlpath='', data=None):
        return self.request('put', urlpath, data)

    def delete(self, urlpath='', data=None):
        return self.request('delete', urlpath, data)

    def request(self, method, urlpath='', data=None):
        headers = {'Content-Type': 'application/json'}
        url = '/'.join([self.url, urlpath])
        LOG.debug(
            "Sending METHOD (%(method)s) URL (%(url)s) JSON (%(data)s)",
            {'method': method, 'url': url, 'data': data})
        return self.session.request(
            method, url=url, headers=headers, data=data, timeout=self.timeout)

    def sendjson(self, method, urlpath, obj):
        """Send json to the OpenDaylight controller."""
        data = jsonutils.dumps(obj, indent=2) if obj else None
        try:
            return self._check_response(
                self.request(method, urlpath, data))
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.error("REST request ( %(method)s ) to "
                          "url ( %(urlpath)s ) is failed. "
                          "Request body : [%(body)s] service",
                          {'method': method,
                           'urlpath': urlpath,
                           'body': obj})

    def send_request(self, operation, service_type, object_type, data):
        """Wrapper method for sendjson()"""
        obj_id = data['id']
        base_path = service_type + '/' + object_type + 's'
        if operation == odl_const.ODL_DELETE:
            urlpath = base_path + '/' + obj_id
            self.try_delete(urlpath)
            return
        elif operation == odl_const.ODL_CREATE:
            urlpath = base_path
            method = 'post'
        elif operation == odl_const.ODL_UPDATE:
            urlpath = base_path + '/' + obj_id
            method = 'put'
        self.sendjson(method, urlpath, {object_type: data})

    def try_delete(self, urlpath):
        response = self.delete(urlpath)
        if response.status_code == requests.codes.not_found:
            # The resource is already removed. ignore 404 gracefully
            LOG.debug("%(urlpath)s doesn't exist", {'urlpath': urlpath})
            return False

        self._check_response(response)
        return True

    def _check_response(self, response):
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            with excutils.save_and_reraise_exception():
                LOG.debug("Exception from ODL: %(e)s %(text)s",
                          {'e': error, 'text': response.text}, exc_info=1)
        else:
            LOG.debug("Got response:\n"
                      "(%(response)s)", {'response': response.text})
            return response


class OpenDaylightRestClientGlobal(object):
    """ODL Rest client as global variable

    The creation of OpenDaylightRestClient needs to be delayed until
    configuration values need to be configured at first.
    """
    def __init__(self):
        super(OpenDaylightRestClientGlobal, self).__init__()
        self._lock = threading.Lock()
        self._client = None

    def get_client(self):
        with self._lock:
            if self._client is None:
                self._client = OpenDaylightRestClient.create_client()
            return self._client
