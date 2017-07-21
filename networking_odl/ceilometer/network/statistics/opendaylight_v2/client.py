#
# Copyright 2017 Ericsson India Global Services Pvt Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import abc

from oslo_log import log
import requests
from requests import auth
import six

from ceilometer.i18n import _


LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class _Base(object):
    """Base class of OpenDaylight REST APIs Clients."""

    @abc.abstractproperty
    def base_url(self):
        """Returns base url for each REST API."""

    def __init__(self, client):
        self.client = client

    def get_statistics(self):
        return self.client.request(self.base_url)


class OpenDaylightRESTAPIFailed(Exception):
    pass


class SwitchStatisticsAPIClient(_Base):
    """OpenDaylight Switch Statistics REST API Client

    Base URL:
      {endpoint}/flow-capable-switches
    """

    base_url = '/flow-capable-switches'


class Client(object):

    def __init__(self, conf, endpoint, params):
        self.switch_statistics = SwitchStatisticsAPIClient(self)
        self._endpoint = endpoint
        self.conf = conf

        self._req_params = self._get_req_params(params)
        self.session = requests.Session()

    def _get_req_params(self, params):
        req_params = {
            'headers': {
                'Accept': 'application/json'
            },
            'timeout': self.conf.http_timeout,
        }

        auth_way = params.get('auth')
        if auth_way in ['basic', 'digest']:
            user = params.get('user')
            password = params.get('password')

            if auth_way == 'basic':
                auth_class = auth.HTTPBasicAuth
            else:
                auth_class = auth.HTTPDigestAuth

            req_params['auth'] = auth_class(user, password)
        return req_params

    def _log_req(self, url):

        curl_command = ['REQ: curl -i -X GET', '"%s"' % (url)]

        if 'auth' in self._req_params:
            auth_class = self._req_params['auth']
            if isinstance(auth_class, auth.HTTPBasicAuth):
                curl_command.append('--basic')
            else:
                curl_command.append('--digest')

            curl_command.append('--user "%s":"***"' % auth_class.username)

        for name, value in six.iteritems(self._req_params['headers']):
            curl_command.append('-H "%s: %s"' % (name, value))

        LOG.debug(' '.join(curl_command))

    @staticmethod
    def _log_res(resp):

        dump = ['RES: \n', 'HTTP %.1f %s %s\n' % (resp.raw.version,
                                                  resp.status_code,
                                                  resp.reason)]
        dump.extend('%s: %s\n' % (k, v)
                    for k, v in six.iteritems(resp.headers))
        dump.append('\n')
        if resp.content:
            dump.extend([resp.content, '\n'])

        LOG.debug(''.join(dump))

    def _http_request(self, url):
        if self.conf.debug:
            self._log_req(url)
        resp = self.session.get(url, **self._req_params)
        if self.conf.debug:
            self._log_res(resp)
        if resp.status_code // 100 != 2:
            raise OpenDaylightRESTAPIFailed(
                _('OpenDaylight API returned %(status)s %(reason)s') %
                {'status': resp.status_code, 'reason': resp.reason})

        return resp.json()

    def request(self, path):

        url = self._endpoint + path
        return self._http_request(url)
