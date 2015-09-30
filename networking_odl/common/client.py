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

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import excutils
import requests


LOG = log.getLogger(__name__)
cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')


class OpenDaylightRestClient(object):

    @classmethod
    def create_client(cls):
        if cfg.CONF.ml2_odl.enable_lightweight_testing:
            LOG.debug("ODL lightweight testing is enabled, ",
                      "returning a OpenDaylightLwtClient instance")

            """Have to import at here, otherwise we create a dependency loop"""
            from networking_odl.common import lightweight_testing as lwt
            cls = lwt.OpenDaylightLwtClient

        return cls(
            cfg.CONF.ml2_odl.url,
            cfg.CONF.ml2_odl.username,
            cfg.CONF.ml2_odl.password,
            cfg.CONF.ml2_odl.timeout)

    def __init__(self, url, username, password, timeout):
        self.url = url
        self.timeout = timeout
        self.auth = (username, password)

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
        return requests.request(
            method, url=url, headers=headers, data=data, auth=self.auth,
            timeout=self.timeout)

    def sendjson(self, method, urlpath, obj):
        """Send json to the OpenDaylight controller."""
        data = jsonutils.dumps(obj, indent=2) if obj else None
        return self._check_rensponse(self.request(method, urlpath, data))

    def try_delete(self, urlpath):
        rensponse = self.delete(urlpath)
        if rensponse.status_code == requests.codes.not_found:
            # The resource is already removed. ignore 404 gracefully
            LOG.debug("%(urlpath)s doesn't exist", {'urlpath': urlpath})
            return False
        else:
            self._check_rensponse(rensponse)
            return True

    def _check_rensponse(self, rensponse):
        try:
            rensponse.raise_for_status()
        except requests.HTTPError as error:
            with excutils.save_and_reraise_exception():
                LOG.debug("Exception from ODL: %(e)s %(text)s",
                          {'e': error, 'text': rensponse.text}, exc_info=1)
        else:
            LOG.debug("Got response:\n"
                      "(%(response)s)", {'response': rensponse.text})
            return rensponse
