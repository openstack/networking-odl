======================
 Enabling in Devstack
======================

1. Download DevStack

2. Copy the sample local.conf over::

     cp devstack/local.conf.example local.conf

3. Optionally, to manually configure this:

   Add this repo as an external repository::

     > cat local.conf
     [[local|localrc]]
     enable_plugin networking-odl http://git.openstack.org/openstack/networking-odl

4. Optionally, to enable support for OpenDaylight L3 router functionality,
   add the below.
   Note: This is only relevant when using old netvirt (ovsdb based, default)::

     > cat local.conf
     [[local|localrc]]
     ODL_L3=True

5. If you need to route the traffic out of the box (e.g. br-ex), set
   ODL_PROVIDER_MAPPINGS to map the physical provider network to device
   mapping, as shown below::

     > cat local.conf
     [[local|localrc]]
     ODL_L3=True
     ODL_PROVIDER_MAPPINGS=${ODL_PROVIDER_MAPPINGS:-br-ex:eth2}    # for old netvirt (ovsdb based)
     ODL_PROVIDER_MAPPINGS=${ODL_PROVIDER_MAPPINGS:-physnet1:eth2} # for new netvirt (vpnservice based)

6. Optionally, to enable support for OpenDaylight with LBaaS V2, add this::

     > cat local.conf
     [[local|localrc]]
     enable_plugin neutron-lbaas http://git.openstack.org/openstack/neutron-lbaas
     enable_service q-lbaasv2
     NEUTRON_LBAAS_SERVICE_PROVIDERV2="LOADBALANCERV2:opendaylight:networking_odl.lbaas.driver_v2.OpenDaylightLbaasDriverV2:default"

7. run ``stack.sh``

8. Note: In a multi-node devstack environment, for each compute node you will
   want to add this to the local.conf file::

     > cat local.conf
     [[local|localrc]]
     enable_plugin networking-odl http://git.openstack.org/openstack/networking-odl
     ODL_MODE=compute

9. Note: In a node using a release of Open vSwitch provided from another source
   than your Linux distribution you have to enable in your local.conf skipping
   of OVS installation step by setting *SKIP_OVS_INSTALL=True*. For example
   when stacking together with `networking-ovs-dpdk
   <https://github.com/openstack/networking-ovs-dpdk/>`_ Neutron plug-in to
   avoid conflicts between openvswitch and ovs-dpdk you have to add this to
   the local.conf file::

     > cat local.conf
     [[local|localrc]]
     enable_plugin networking-ovs-dpdk http://git.openstack.org/openstack/networking-ovs-dpdk
     enable_plugin networking-odl http://git.openstack.org/openstack/networking-odl
     SKIP_OVS_INSTALL=True
     Q_ML2_PLUGIN_MECHANISM_DRIVERS=opendaylight

10. Note: Optionally, to use the new netvirt implementation
    (netvirt-vpnservice-openstack), add the following to the local.conf file
    (only allinone topology is currently supported by devstack, since tunnel
    endpoints are not automatically configured). For tunnel configurations
    after loading devstack, please refer to this guide
    https://wiki.opendaylight.org/view/Netvirt:_L2Gateway_HowTo#Configuring_Tunnels::

      > cat local.conf
      [[local|localrc]]
      ODL_NETVIRT_KARAF_FEATURE=odl-restconf-all,odl-aaa-authn,odl-dlux-core,odl-mdsal-apidocs,odl-netvirt-vpnservice-openstack
      ODL_BOOT_WAIT_URL=restconf/operational/network-topology:network-topology/ # Workaround since netvirt:1 no longer exists in DS!

11. Note: Enable Quality Of Service (QoS) with OpenDaylight Backend
    enable the qos service plugin by adding qos to service_plugins::

      > in /etc/neutron/neutron.conf
      service_plugins = qos, odl-router

    enable notification driver in neutron.conf::

      > in /etc/neutron/neutron.conf
      [qos]
      notification_drivers = odl-qos

    enable qos extension driver in ml2 conf::

      > in /etc/neutron/plugins/ml2/ml2_conf.ini
      extensions_drivers = qos, port_security

    restart neutron service q-svc
