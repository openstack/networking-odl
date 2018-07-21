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

from oslo_log import log
from six.moves import urllib_parse as urlparse

from ceilometer import keystone_client
from ceilometer.network.statistics import driver
from networking_odl.ceilometer.network.statistics.opendaylight_v2 import client


LOG = log.getLogger(__name__)
INT64_MAX_VALUE = (2 ** 64 / 2 - 1)


class OpenDaylightDriver(driver.Driver):
    """Driver of network info collector from OpenDaylight.

    This driver uses resources in "/etc/ceilometer/polling.yaml".
    Resource requires below conditions:

    * resource is url
    * scheme is "opendaylight.v2"

    This driver can be configured via query parameters.
    Supported parameters:

    * scheme:
      The scheme of request url to OpenDaylight REST API endpoint.
      (default http)
    * auth:
      Auth strategy of http.
      This parameter can be set basic or digest.(default None)
    * user:
      This is username that is used by auth.(default None)
    * password:
      This is password that is used by auth.(default None)

    e.g.::

      opendaylight.v2://127.0.0.1:8080/controller/statistics
      ?auth=basic&user=admin&password=admin&scheme=http

    In this case, the driver send request to below URLs:

      http://127.0.0.1:8080/controller/statistics/flow-capable-switches

    Example JSON response from OpenDaylight
    {
        flow_capable_switches: [{
            packet_in_messages_received: 501,
            packet_out_messages_sent: 300,
            ports: 1,
            flow_datapath_id: 55120148545607,
            tenant_id: ADMIN_ID,
            switch_port_counters: [{
                bytes_received: 1000,
                bytes_sent: 1000,
                duration: 600,
                packets_internal_received: 100,
                packets_internal_sent: 200,
                packets_received: 100,
                packets_received_drop: 0,
                packets_received_error: 0,
                packets_sent: 100,
                port_id: 4,
                tenant_id: PORT_1_TENANT_ID,
                uuid: PORT_1_ID
            }],
            table_counters: [{
                flow_count: 90,
                table_id: 0
            }]
        }]
    }

    """

    admin_project_id = None

    @staticmethod
    def _get_int_sample(key, statistic, resource_id,
                        resource_meta, tenant_id):
        if key not in statistic:
            return None
        value = int(statistic[key])
        if not (0 <= value <= INT64_MAX_VALUE):
            value = 0
        return value, resource_id, resource_meta, tenant_id

    def _prepare_cache(self, endpoint, params, cache):

        if 'network.statistics.opendaylight_v2' in cache:
            return cache['network.statistics.opendaylight_v2']

        data = {}

        odl_params = {}
        if 'auth' in params:
            odl_params['auth'] = params['auth'][0]
        if 'user' in params:
            odl_params['user'] = params['user'][0]
        if 'password' in params:
            odl_params['password'] = params['password'][0]
        cs = client.Client(self.conf, endpoint, odl_params)

        if not self.admin_project_id:
            try:
                ks_client = keystone_client.get_client(self.conf)
                project = ks_client.projects.find(name='admin')
                if project:
                    self.admin_project_id = project.id
            except Exception:
                LOG.exception('Unable to fetch admin tenant id')
                cache['network.statistics.opendaylight_v2'] = data
                return data

        try:
            # get switch statistics
            data['switch'] = cs.switch_statistics.get_statistics()
            data['admin_tenant_id'] = self.admin_project_id
        except client.OpenDaylightRESTAPIFailed:
            LOG.exception('OpenDaylight REST API Failed. ')
        except Exception:
            LOG.exception('Failed to connect to OpenDaylight'
                          ' REST API')

        cache['network.statistics.opendaylight_v2'] = data

        return data

    def get_sample_data(self, meter_name, parse_url, params, cache):

        extractor = self._get_extractor(meter_name)
        if extractor is None:
            # The way to getting meter is not implemented in this driver or
            # OpenDaylight REST API has not api to getting meter.
            return None

        iter = self._get_iter(meter_name)
        if iter is None:
            # The way to getting meter is not implemented in this driver or
            # OpenDaylight REST API has not api to getting meter.
            return None

        parts = urlparse.ParseResult(params.get('scheme', ['http'])[0],
                                     parse_url.netloc,
                                     parse_url.path,
                                     None,
                                     None,
                                     None)
        endpoint = urlparse.urlunparse(parts)

        data = self._prepare_cache(endpoint, params, cache)

        samples = []
        if data:
            for sample in iter(extractor, data):
                if sample is not None:
                    # set controller name to resource_metadata
                    sample[2]['controller'] = 'OpenDaylight_V2'
                    samples.append(sample)

        return samples

    def _get_iter(self, meter_name):
        if meter_name == 'switch' or meter_name == 'switch.ports':
            return self._iter_switch
        elif meter_name.startswith('switch.table'):
            return self._iter_table
        elif meter_name.startswith('switch.port'):
            return self._iter_switch_port
        elif meter_name.startswith('port'):
            return self._iter_port
        return None

    def _get_extractor(self, meter_name):
        if (meter_name == 'switch.port' or
                meter_name.startswith('switch.port.')):
            meter_name = meter_name.split('.', 1)[1]
        method_name = '_' + meter_name.replace('.', '_')
        return getattr(self, method_name, None)

    @staticmethod
    def _iter_switch(extractor, data):
        for switch in data['switch']['flow_capable_switches']:
            yield (extractor(switch, str(switch['flow_datapath_id']), {},
                             (switch.get('tenant_id') or
                              data['admin_tenant_id'])))

    @staticmethod
    def _switch(statistic, resource_id,
                resource_meta, tenant_id):
        return 1, resource_id, resource_meta, tenant_id

    @staticmethod
    def _switch_ports(statistic, resource_id,
                      resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'ports', statistic, resource_id,
            resource_meta, tenant_id)

    @staticmethod
    def _iter_switch_port(extractor, data):
        for switch in data['switch']['flow_capable_switches']:
            if 'switch_port_counters' in switch:
                switch_id = str(switch['flow_datapath_id'])
                tenant_id = (switch.get('tenant_id') or
                             data['admin_tenant_id'])
                for port_statistic in switch['switch_port_counters']:
                    port_id = port_statistic['port_id']
                    resource_id = '%s:%d' % (switch_id, port_id)
                    resource_meta = {'switch': switch_id,
                                     'port_number_on_switch': port_id}
                    if 'uuid' in port_statistic:
                        neutron_port_id = port_statistic['uuid']
                        resource_meta['neutron_port_id'] = neutron_port_id
                    yield extractor(port_statistic, resource_id,
                                    resource_meta, tenant_id)

    @staticmethod
    def _iter_port(extractor, data):
        resource_meta = {}
        for switch in data['switch']['flow_capable_switches']:
            if 'switch_port_counters' in switch:
                for port_statistic in switch['switch_port_counters']:
                    if 'uuid' in port_statistic:
                        resource_id = port_statistic['uuid']
                        tenant_id = port_statistic.get('tenant_id')
                        yield extractor(
                            port_statistic, resource_id, resource_meta,
                            tenant_id or data['admin_tenant_id'])

    @staticmethod
    def _port(statistic, resource_id, resource_meta, tenant_id):
        return 1, resource_id, resource_meta, tenant_id

    @staticmethod
    def _port_uptime(statistic, resource_id,
                     resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'duration', statistic, resource_id,
            resource_meta, tenant_id)

    @staticmethod
    def _port_receive_packets(statistic, resource_id,
                              resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'packets_received', statistic, resource_id,
            resource_meta, tenant_id)

    @staticmethod
    def _port_transmit_packets(statistic, resource_id,
                               resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'packets_sent', statistic, resource_id,
            resource_meta, tenant_id)

    @staticmethod
    def _port_receive_bytes(statistic, resource_id,
                            resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'bytes_received', statistic, resource_id,
            resource_meta, tenant_id)

    @staticmethod
    def _port_transmit_bytes(statistic, resource_id,
                             resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'bytes_sent', statistic, resource_id,
            resource_meta, tenant_id)

    @staticmethod
    def _port_receive_drops(statistic, resource_id,
                            resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'packets_received_drop', statistic, resource_id,
            resource_meta, tenant_id)

    @staticmethod
    def _port_receive_errors(statistic, resource_id,
                             resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'packets_received_error', statistic,
            resource_id, resource_meta, tenant_id)

    @staticmethod
    def _iter_table(extractor, data):
        for switch_statistic in data['switch']['flow_capable_switches']:
            if 'table_counters' in switch_statistic:
                switch_id = str(switch_statistic['flow_datapath_id'])
                tenant_id = (switch_statistic.get('tenant_id') or
                             data['admin_tenant_id'])
                for table_statistic in switch_statistic['table_counters']:
                    resource_meta = {'switch': switch_id}
                    resource_id = ("%s:table:%d" %
                                   (switch_id, table_statistic['table_id']))
                    yield extractor(table_statistic, resource_id,
                                    resource_meta, tenant_id)

    @staticmethod
    def _switch_table_active_entries(statistic, resource_id,
                                     resource_meta, tenant_id):
        return OpenDaylightDriver._get_int_sample(
            'flow_count', statistic, resource_id,
            resource_meta, tenant_id)
