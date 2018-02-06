Host Configuration
==================

Overview
--------

ODL is agentless configuration. In this scenario Host Configuration is used
to specify the physical host type and other configurations for the host
system. This information is populated by the Cloud Operator is in OVSDB in
Open_vSwitch configuration data in the external_ids field as a key value pair.
This information is then read by ODL and made available to networking-odl
through REST API. Networking-odl populates this information in agent_db in
Neutron and is then used by Neutron scheduler. This information is required
for features like Port binding and Router scheduling.

Refer to this link for detailed design for this feature.

https://docs.google.com/presentation/d/1kq0elysCDEmIWs3omTi5RoXTSBbrewn11Je2d26cI4M/edit?pref=2&pli=1#slide=id.g108988d1e3_0_6

Related ODL changes:

https://git.opendaylight.org/gerrit/#/c/36767/

https://git.opendaylight.org/gerrit/#/c/40143/

Host Configuration fields
-------------------------

- **host-id**

  This represents host identification string. This string will be stored in
  external_ids field with the key as odl_os_hostconfig_hostid.
  Refer to Neutron config definition for host field for details on this field.

  https://docs.openstack.org/kilo/config-reference/content/section_neutron.conf.html

- **host-type**

  The field is for type of the node. This value corresponds to agent_type in
  agent_db. Example value are "ODL L2" and "ODL L3" for Compute and Network
  node respectively. Same host can be configured to have multiple
  configurations and can therefore can have both L2, L3 and other
  configurations at the same time. This string will be populated by ODL based
  on the configurations available on the host. See example in section below.

- **config**

  This is the configuration data for the host type. Since same node can be
  configured to store multiple configurations different external_ids key value
  pair are used to store these configuration. The external_ids with keys as
  odl_os_hostconfig_config_odl_XXXXXXXX store different configurations.
  8 characters after the suffix odl_os_hostconfig_config_odl are host type.
  ODL extracts these characters and store that as the host-type fields. For
  example odl_os_hostconfig_config_odl_l2, odl_os_hostconfig_config_odl_l3 keys
  are used to provide L2 and L3 configurations respectively. ODL will extract
  "ODL L2" and "ODL L3" as host-type field from these keys and populate
  host-type field.

Config is a Json string. Some examples of config:

OVS configuration example::

   {"supported_vnic_types": [{
            "vnic_type": "normal",
            "vif_type": "ovs",
            "vif_details": "{}"
        }]
        "allowed_network_types": ["local", "gre", "vlan", "vxlan"]",
        "bridge_mappings": {"physnet1":"br-ex"}
   }"

OVS SR-IOV Hardware Offload configuration example::

   {"supported_vnic_types": [{
            "vnic_type": "normal",
            "vif_type": "ovs",
            "vif_details": "{}"},
            {"vnic_type": "direct",
            "vif_type": "ovs",
            "vif_details": "{}"}
        }]
        "allowed_network_types": ["local", "gre", "vlan", "vxlan"]",
        "bridge_mappings": {"physnet1":"br-ex"}
   }"

OVS_DPDK configuration example::

   {"supported_vnic_types": [{
            "vnic_type": "normal",
            "vif_type": "vhostuser",
            "vif_details": {
                "uuid": "TEST_UUID",
                "has_datapath_type_netdev": True,
                "support_vhost_user": True,
                "port_prefix": "vhu",
                # Assumption: /var/run mounted as tmpfs
                "vhostuser_socket_dir": "/var/run/openvswitch",
                "vhostuser_ovs_plug": True,
                "vhostuser_mode": "client",
                "vhostuser_socket": "/var/run/openvswitch/vhu$PORT_ID"}
        }]
        "allowed_network_types": ["local", "gre", "vlan", "vxlan"]",
        "bridge_mappings": {"physnet1":"br-ex"}
   }"

VPP configuration example::

   { {"supported_vnic_types": [
        {"vnic_type": "normal",
         "vif_type": "vhostuser",
         "vif_details": {
             "uuid": "TEST_UUID",
             "has_datapath_type_netdev": True,
             "support_vhost_user": True,
             "port_prefix": "socket_",
             "vhostuser_socket_dir": "/tmp",
             "vhostuser_ovs_plug": True,
             "vhostuser_mode": "server",
             "vhostuser_socket": "/tmp/socket_$PORT_ID"
         }}],
        "allowed_network_types": ["local", "vlan", "vxlan", "gre"],
        "bridge_mappings": {"physnet1": "br-ex"}}}

**Host Config URL**

Url : https://ip:odlport/restconf/operational/neutron:neutron/hostconfigs/

**Commands to setup host config in OVSDB**
::

 export OVSUUID=$(ovs-vsctl get Open_vSwitch . _uuid)
 ovs-vsctl set Open_vSwitch $OVSUUID external_ids:odl_os_hostconfig_hostid=test_host
 ovs-vsctl set Open_vSwitch $OVSUUID external_ids:odl_os_hostconfig_config_odl_l2 =
 "{"supported_vnic_types": [{"vnic_type": "normal", "vif_type": "ovs", "vif_details": {} }], "allowed_network_types": ["local"], "bridge_mappings": {"physnet1":"br-ex"}}"

Example for host configuration
-------------------------------

::

  {
  "hostconfigs": {
    "hostconfig": [
      {
        "host-id": "test_host1",
        "host-type": "ODL L2",
        "config":
        "{"supported_vnic_types": [{
            "vnic_type": "normal",
            "vif_type": "ovs",
            "vif_details": {}
        }]
        "allowed_network_types": ["local", "gre", "vlan", "vxlan"],
        "bridge_mappings": {"physnet1":"br-ex"}}"
      },
      {
        "host-id": "test_host2",
        "host-type": "ODL L3",
        "config": {}
      }]
    }
  }
