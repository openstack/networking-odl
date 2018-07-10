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

from networking_odl._i18n import _


odl_opts = [
    cfg.StrOpt('url',
               help=_("HTTP URL of OpenDaylight REST interface.")),
    cfg.StrOpt('username',
               help=_("HTTP username for authentication.")),
    cfg.StrOpt('password', secret=True,
               help=_("HTTP password for authentication.")),
    cfg.IntOpt('timeout', default=10,
               help=_("HTTP timeout in seconds.")),
    cfg.IntOpt('session_timeout', default=30,
               help=_("Tomcat session timeout in minutes.")),
    cfg.FloatOpt('sync_timeout', default=10,
                 help=_("Sync thread timeout in seconds or fraction.")),
    cfg.IntOpt('retry_count', default=5,
               help=_("Number of times to retry a row before failing.")),
    cfg.IntOpt('maintenance_interval', default=300,
               help=_("Journal maintenance operations interval in seconds.")),
    cfg.IntOpt('completed_rows_retention', default=0,
               help=_("Time to keep completed rows (in seconds)."
                      "For performance reasons it's not recommended to "
                      "change this from the default value (0) which "
                      "indicates completed rows aren't kept."
                      "This value will be checked every maintenance_interval "
                      "by the cleanup thread. To keep completed rows "
                      "indefinitely, set the value to -1")),
    cfg.BoolOpt('enable_lightweight_testing',
                default=False,
                help=_('Test without real ODL.')),
    cfg.StrOpt('port_binding_controller',
               default='pseudo-agentdb-binding',
               help=_('Name of the controller to be used for port binding.')),
    cfg.IntOpt('processing_timeout', default='100',
               help=_("Time in seconds to wait before a "
                      "processing row is marked back to pending.")),
    cfg.StrOpt('odl_hostconf_uri',
               help=_("Path for ODL host configuration REST interface"),
               default="/restconf/operational/neutron:neutron/hostconfigs"),
    cfg.IntOpt('restconf_poll_interval', default=30,
               help=_("Poll interval in seconds for getting ODL hostconfig")),
    cfg.BoolOpt('enable_websocket_pseudo_agentdb', default=False,
                help=_('Enable websocket for pseudo-agent-port-binding.')),
    cfg.IntOpt('odl_features_retry_interval', default=5,
               help=_("Wait this many seconds before retrying the odl features"
                      " fetch")),
    cfg.ListOpt('odl_features',
                help='A list of features supported by ODL.'),
    cfg.StrOpt('odl_features_json',
               help='Features supported by ODL, in the json format returned'
               'by ODL. Note: This config option takes precedence over'
               'odl_features.'),
    cfg.BoolOpt('enable_dhcp_service', default=False,
                help=_('Enables the networking-odl driver to supply special'
                       ' neutron ports of "dhcp" type to OpenDaylight'
                       ' Controller for its use in providing DHCP Service.')),
]

cfg.CONF.register_opts(odl_opts, "ml2_odl")


def list_opts():
    return [('ml2_odl', odl_opts)]
