/*
 * Copyright (c) 2016 OpenStack Foundation
 * All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 *
 * $nodejs odl_teststub.js
 *
 * local.conf or ml2_conf.ini should be set to the following:
 *
 * [ml2_odl]
 * port_binding_controller = pseudo-agentdb-binding
 * password = admin
 * username = admin
 * url = http://localhost:8080/controller/nb/v2/neutron
 * restconf_uri = http://localhost:8125/ # for this stub
 *
 * To test with ODL *end to end* use below URL for restconf_uri and configure
 * ovsdb external_ids using the test script: config-ovs-external_ids.sh
 *
 * http://localhost:8181/restconf/operational/neutron:neutron/hostconfigs
 */

var http = require('http');

const PORT=8125;

__test_odl_hconfig = {"hostconfigs": {"hostconfig": [
            {"host-id": "devstack",
             "host-type": "ODL L2",
             "config": {
                 "supported_vnic_types": [
                     {"vnic_type": "normal",
                      "vif_type": "ovs",
                      "vif_details": {}}],
                 "allowed_network_types": ["local", "vlan", "vxlan", "gre"],
                 "bridge_mappings": {"physnet1":"br-ex"}
                 }
             }]
        }}


function handleRequest(req, res){
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify(__test_odl_hconfig));
}

var server = http.createServer(handleRequest);

server.listen(PORT, function(){
                console.log("Server listening on: http://localhost:%s", PORT);
                });
