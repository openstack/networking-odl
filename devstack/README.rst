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

4. Optionally, to enable support for OpenDaylight L3 router functionality, add the
   below::

     > cat local.conf
     disable_service q-l3
     Q_L3_ENABLED=True
     ODL_L3=True
     [[post-config|$NEUTRON_CONF]]
     [DEFAULT]
     service_plugins = networking_odl.l3.l3_odl.OpenDaylightL3RouterPlugin

5. Optionally, to enable support for OpenDaylight with LBaaS V2, add this::

     > cat local.conf
     enable_plugin neutron-lbaas http://git.openstack.org/openstack/neutron-lbaas
     enable_service q-lbaasv2
     NEUTRON_LBAAS_SERVICE_PROVIDERV2="LOADBALANCERV2:opendaylight:networking_odl.lbaas.driver_v2.OpenDaylightLbaasDriverV2:default"

6. To enable L3 router functionality and LBaaS at the same time, add the following::

     > cat local.conf
     disable_service q-l3
     enable_plugin neutron-lbaas http://git.openstack.org/openstack/neutron-lbaas
     enable_service q-lbaasv2
     NEUTRON_LBAAS_SERVICE_PROVIDERV2="LOADBALANCERV2:opendaylight:networking_odl.lbaas.driver_v2.OpenDaylightLbaasDriverV2:default"
     [[post-config|$NEUTRON_CONF]]
     [DEFAULT]
     service_plugins = networking_odl.l3.l3_odl.OpenDaylightL3RouterPlugin,neutron_lbaas.services.loadbalancer.plugin.LoadBalancerPluginv2

7. run ``stack.sh``

8. Note: In a multi-node devstack environment, for each compute node you will want to add this
   to the local.conf file::

     > cat local.conf
     enable_plugin networking-odl http://git.openstack.org/openstack/networking-odl
     ODL_MODE=compute
