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
   add the below::

     > cat local.conf
     [[local|localrc]]
     ODL_L3=True

   .. note::

      This is only relevant when using old netvirt (ovsdb based, default).

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

11. Note: To enable Quality Of Service (QoS) with OpenDaylight Backend,
    add the following lines in neutron.conf::

      > in /etc/neutron/neutron.conf
      service_plugins = qos, odl-router

    enable qos extension driver in ml2 conf::

      > in /etc/neutron/plugins/ml2/ml2_conf.ini
      extensions_drivers = qos, port_security

    restart neutron service q-svc


12. Note: legacy netvirt specific options

    - OVS conntrack support

      :variable: ODL_LEGACY_NETVIRT_CONNTRACK By default it's False for
                 compatibility and version requirements.

      - version requirement

        :ODL version: Boron release or later.
                      (ODL legacy netvirt support is from Beryllium. But
                      networking-odl devstack supports Boron+)

        :OVS version: 2.5 or later

      enable OVS conntrack support::

        > cat local.conf
        [[local|localrc]]
        ODL_LEGACY_NETVIRT_CONNTRACK=True

13. Note: To enable Vlan Aware VMs (Trunk) with OpenDaylight Backend,
    make the following entries in local.conf::

     > cat local.conf
     [[local|localrc]]
     Q_SERVICE_PLUGIN_CLASSES=trunk

14. Enabling L2Gateway Backend for OpenDaylight

- The package networking-l2gw must be installed as a pre-requisite.

  So include in your localrc (or local.conf) the following::

    enable_plugin networking-l2gw http://git.openstack.org/openstack/networking-l2gw
    enable_service l2gw-plugin
    NETWORKING_L2GW_SERVICE_DRIVER=L2GW:OpenDaylight:networking_odl.l2gateway.driver_v2.OpenDaylightL2gwDriver:default

- Now stack up Devstack and after stacking completes, we are all set to use
  l2gateway-as-a-service with OpenDaylight.

15. Note: To enable Service Function Chaining support driven by networking-sfc,
    the following steps have to be taken:

    - local.conf should contain the following lines::

        # enable our plugin:
        enable_plugin networking-odl https://github.com/openstack/networking-odl.git

        # enable the networking-sfc plugin:
        enable_plugin networking-sfc https://github.com/openstack/networking-sfc.git

        # enable the odl-netvirt-sfc Karaf feature in OpenDaylight
        ODL_NETVIRT_KARAF_FEATURE+=,odl-netvirt-sfc

        # enable the networking-sfc OpenDaylight driver pair
        [[post-config|$NEUTRON_CONF]]
        [sfc]
        drivers = odl_v2
        [flowclassifier]
        drivers = odl_v2

    - A special commit of Open vSwitch should be compiled and installed
      (containing compatible NSH OpenFlow support). This isn't
      done automatically by networking-odl or DevStack, so the user has to
      manually install. Please follow the instructions in:
      https://wiki.opendaylight.org/view/Service_Function_Chaining:Main#Building_Open_vSwitch_with_VxLAN-GPE_and_NSH_support

    - Carbon is the recommended and latest version of OpenDaylight to use,
      you can specify it by adding the following to local.conf::

        ODL_RELEASE=carbon-snapshot-0.6

    - To clarify, OpenDaylight doesn't have to be running/installed before
      stacking with networking-odl (and it shouldn't). The networking-odl
      DevStack plugin will download and start OpenDaylight automatically.
      However, it will not fetch the correct Open vSwitch version, so the
      instructions above and the usage of ``SKIP_OVS_INSTALL`` are important.

16. To enable BGPVPN driver to use with OpenDaylight controller
    Include the following lines in your localrc (or local.conf)::

      enable_plugin networking-bgpvpn https://git.openstack.org/openstack/networking-bgpvpn.git

      [[post-config|$NETWORKING_BGPVPN_CONF]]
      [service_providers]
      service_provider=BGPVPN:OpenDaylight:networking_odl.bgpvpn.odl_v2.OpenDaylightBgpvpnDriver:default

    and then stack up your devstack.

17. To enable DHCP Service in OpenDaylight deployments with Openstack,
    please use::

      [[local|localrc]]
      ODL_DHCP_SERVICE=True

18. To enable ODL with OVS hardware Offload support
    please use::

      [[local|localrc]]
      ODL_OVS_HOSTCONFIGS_OPTIONS="--noovs_dpdk --debug --ovs_sriov_offload"

    Note: OVS offload support minimal version requirments -
        Linux kernel from version 4.12
        OVS from version 2.8.0
        ODL from version Nitrogen

19. For development enviornment, if opendaylight installation is not required
    for stack.sh then a parameter ODL_INSTALL should be set to False. By
    default it is set to True therefore it is backward compatible with
    gate and already existing scripts::

      [[local|localrc]]
      ODL_INSTALL=False
