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
from six.moves import urllib_parse as urlparse

from networking_odl.common import constants as odl_const

cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')


def try_del(d, keys):
    """Ignore key errors when deleting from a dictionary."""
    for key in keys:
        try:
            del d[key]
        except KeyError:
            pass


def make_url_object(object_type):
    obj_pl = odl_const.RESOURCE_URL_MAPPINGS.get(object_type, None)
    if obj_pl is None:
        obj_pl = neutronify(object_type + 's')
    return obj_pl


# TODO(manjeets) consolidate this method with make_url_object
def neutronify(name):
    """Adjust the resource name for use with Neutron's API"""
    return name.replace('_', '-')


def get_odl_url(path=''):
    '''Make a URL for some ODL resource (path)'''
    purl = urlparse.urlsplit(cfg.CONF.ml2_odl.url)
    features_url = urlparse.urlunparse((
        purl.scheme, purl.netloc, path, '', '', ''))
    return features_url
