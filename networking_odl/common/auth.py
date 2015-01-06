# Copyright (c) 2013-2014 OpenStack Foundation
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

import time

import requests

from networking_odl.common import constants
from networking_odl.common import exceptions as exc


class JsessionId(requests.auth.AuthBase):

    """Attaches the JSESSIONID and JSESSIONIDSSO cookies to an HTTP Request.

    If the cookies are not available or when the session expires, a new
    set of cookies are obtained.
    """

    def __init__(self, url, username, password, timeout):
        """Initialization function for JsessionId."""

        # NOTE(kmestery) The 'limit' paramater is intended to limit how much
        # data is returned from ODL. This is not implemented in the Hydrogen
        # release of OpenDaylight, but will be implemented in the Helium
        # timeframe. Hydrogen will silently ignore this value.
        self.url = str(url) + '/' + constants.ODL_NETWORKS + '?limit=1'
        self.username = username
        self.password = password
        self.auth_cookies = None
        self.last_request = None
        self.expired = None
        self.session_timeout = timeout * 60
        self.session_deadline = 0

    def obtain_auth_cookies(self):
        """Make a REST call to obtain cookies for ODL authenticiation."""

        try:
            r = requests.get(self.url, auth=(self.username, self.password))
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise exc.OpendaylightAuthError(msg=_("Failed to authenticate"
                                                  " with OpenDaylight: %s"
                                                  ) % e)
        except requests.exceptions.Timeout as e:
            raise exc.OpendaylightAuthError(msg=_("Authentication Timed"
                                                  " Out: %s") % e)

        jsessionid = r.cookies.get('JSESSIONID')
        jsessionidsso = r.cookies.get('JSESSIONIDSSO')
        if jsessionid and jsessionidsso:
            self.auth_cookies = dict(JSESSIONID=jsessionid,
                                     JSESSIONIDSSO=jsessionidsso)

    def __call__(self, r):
        """Verify timestamp for Tomcat session timeout."""

        if time.time() > self.session_deadline:
            self.obtain_auth_cookies()
        self.session_deadline = time.time() + self.session_timeout
        r.prepare_cookies(self.auth_cookies)
        return r
