# Copyright (c) 2017 OpenStack Foundation
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

import copy
import itertools
import time

from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils
from requests import exceptions

from networking_odl.common import client as odl_client
from networking_odl.common import utils


cfg.CONF.import_group('ml2_odl', 'networking_odl.common.config')
LOG = log.getLogger(__name__)

OPERATIONAL_PORT_STATUS = 'operational-port-status'

EMPTY_FEATURES = {}

feature_configs = copy.copy(EMPTY_FEATURES)


def init():
    '''initialize odl_features.

    Initialize odl_features. Try first from configuration and then try pulling
    via rest call from ODL.
    '''

    global feature_configs
    feature_configs = None

    if cfg.CONF.ml2_odl.odl_features_json is not None:
        json = jsonutils.loads(cfg.CONF.ml2_odl.odl_features_json)
        feature_configs = _load_features(json)
        return

    if cfg.CONF.ml2_odl.odl_features is not None:
        feature_configs = {feature: '' for feature
                           in cfg.CONF.ml2_odl.odl_features}
        return

    wait_interval = cfg.CONF.ml2_odl.odl_features_retry_interval

    for times_tried in itertools.count():
        feature_configs = _fetch_features()
        if feature_configs is not None:
            break
        LOG.warning('Failed to retrieve ODL features, attempt %i', times_tried)
        time.sleep(wait_interval)


def has(feature):
    return feature in feature_configs


def get_config(feature):
    return feature_configs[feature]


def deinit():
    '''Set odl_features back to it's pre-initlialized '''
    global feature_configs
    feature_configs = copy.copy(EMPTY_FEATURES)


def _load_features(json):
    """parse and save features from json"""
    features = json['features']
    if 'feature' not in features:
        return copy.copy(EMPTY_FEATURES)

    # documentation on the JSON received can be found at:
    # https://github.com/opendaylight/neutron/blob/master/model/src/main/yang/neutron-extensions.yang
    LOG.info('Retrieved ODL features %s', features)
    response = {}
    for feature in features['feature']:
        cfg = feature.get('configuration', '')
        response[feature['service-provider-feature'].split(':')[1]] = cfg
    return response


def _fetch_features():
    '''Fetch the list of features declared by ODL.

    This function should be called once during initialization
    '''

    path = 'restconf/operational/neutron:neutron/neutron:features'
    features_url = utils.get_odl_url(path)

    client = odl_client.OpenDaylightRestClient.create_client(features_url)
    try:
        response = client.request('get')
    except exceptions.ConnectionError:
        LOG.error("Error connecting to ODL to retrieve features",
                  exc_info=True)
        return None

    if response.status_code == 400:
        LOG.debug('ODL does not support feature negotiation')
        return copy.copy(EMPTY_FEATURES)

    if response.status_code == 404:
        LOG.debug('No features configured')
        return copy.copy(EMPTY_FEATURES)

    if response.status_code != 200:
        LOG.warning('error fetching features: %i',
                    response.status_code)
        return None

    return _load_features(response.json())
