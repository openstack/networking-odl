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
     [[local|localrc]]
     ODL_L3=True

5. If you need to route the traffic out of the box (e.g. br-ex), set
   ODL_PROVIDER_MAPPINGS to map the interface, as shown below.

     > cat local.conf
     [[local|localrc]]
     ODL_L3=True
     ODL_PROVIDER_MAPPINGS=${ODL_PROVIDER_MAPPINGS:-br-ex:eth2}

6. Optionally, to enable support for OpenDaylight with LBaaS V2, add this::

     > cat local.conf
     enable_plugin neutron-lbaas http://git.openstack.org/openstack/neutron-lbaas
     enable_service q-lbaasv2
     NEUTRON_LBAAS_SERVICE_PROVIDERV2="LOADBALANCERV2:opendaylight:networking_odl.lbaas.driver_v2.OpenDaylightLbaasDriverV2:default"

7. run ``stack.sh``

8. Note: In a multi-node devstack environment, for each compute node you will want to add this
   to the local.conf file::

     > cat local.conf
     enable_plugin networking-odl http://git.openstack.org/openstack/networking-odl
     ODL_MODE=compute
