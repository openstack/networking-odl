.. _installation:

Installation
============

The ``networking-odl`` repository includes integration with DevStack that
enables creation of a simple OpenDaylight (ODL) development and test
environment. This document discusses what is required for manual installation
and integration into a production OpenStack deployment tool of conventional
architectures that include the following types of nodes:

* Controller - Runs OpenStack control plane services such as REST APIs
  and databases.

* Network - Provides connectivity between provider (public) and project
  (private) networks.  Services provided include layer-3 (routing), DHCP, and
  metadata agents. Layer-3 agent is optional. When using netvirt (vpnservice)
  DHCP/metadata are optional.

* Compute - Runs the hypervisor and layer-2 agent for the Networking
  service.

ODL Installation
----------------

http://docs.opendaylight.org provides manual and general documentation for ODL

Review the following documentation regardless of install scenario:

* `ODL installation <http://docs.opendaylight.org/en/latest/getting-started-guide/installing_opendaylight.html>`_.

* `OpenDaylight with OpenStack <http://docs.opendaylight.org/en/latest/opendaylight-with-openstack/index.html>`_.

Choose and review one of the following installation scenarios:

* `GBP with OpenStack <http://docs.opendaylight.org/en/latest/opendaylight-with-openstack/openstack-with-gbp.html>`_.
  OpenDaylight Group Based Policy allows users to express network configuration
  in a declarative rather than imperative way. Often described as asking for
  "what you want", rather than "how you can do it", Group Based Policy achieves
  this by implementing an Intent System. The Intent System is a process around
  an intent driven data model and contains no domain specifics but is capable
  of addressing multiple semantic definitions of intent.

* `OVSDB with OpenStack <http://docs.opendaylight.org/en/latest/opendaylight-with-openstack/openstack-with-ovsdb.html>`_.
  OpenDaylight OVSDB allows users to take advantage of Network Virtualization
  using OpenDaylight SDN capabilities whilst utilizing OpenvSwitch. The stack
  includes a Neutron Northbound, a Network Virtualization layer, an OVSDB
  southbound plugin, and an OpenFlow southbound plugin.

* `VTN with OpenStack <http://docs.opendaylight.org/en/latest/opendaylight-with-openstack/openstack-with-vtn.html>`_.
  OpenDaylight Virtual Tenant Network (VTN) is an application that provides
  multi-tenant virtual network on an SDN controller.  VTN Manager is
  implemented as one plugin to the OpenDaylight controller and provides a REST
  interface to create/update/delete VTN components. It provides an
  implementation of Openstack L2 Network Functions API.

Networking-odl Installation
---------------------------

.. code-block:: console

   # sudo pip install networking-odl

.. note::

   pip need to be installed before running above command.


Networking-odl Configuration
----------------------------

All related neutron services need to be restarted after configuration change.

#. Configure Openstack neutron server. The neutron server implements ODL as an
   ML2 driver. Edit the ``/etc/neutron/neutron.conf`` file:

   * Enable the ML2 core plug-in.

     .. code-block:: ini

        [DEFAULT]
        ...
        core_plugin = neutron.plugins.ml2.plugin.Ml2Plugin

   * (Optional) Enable ODL L3 router, if QoS feature is desired,
     then qos should be appended to service_plugins

     .. code-block:: ini

        [DEFAULT]
        ...
        service_plugins = odl-router_v2


#. Configure the ML2 plug-in. Edit the
   ``/etc/neutron/plugins/ml2/ml2_conf.ini`` file:

   * Configure the ODL mechanism driver, network type drivers, self-service
     (tenant) network types, and enable extension drivers(optional).

     .. code-block:: ini

        [ml2]
        ...
        mechanism_drivers = opendaylight_v2
        type_drivers = local,flat,vlan,vxlan
        tenant_network_types = vxlan
        extension_drivers = port_security, qos

     .. note::

        The enabling of extension_driver qos is optional, it should be
        enabled if service_plugins for qos is also enabled.

   * Configure the vxlan range.

     .. code-block:: ini

        [ml2_type_vxlan]
        ...
        vni_ranges = 1:1000

   * Optionally, enable support for VLAN provider and self-service
     networks on one or more physical networks. If you specify only
     the physical network, only administrative (privileged) users can
     manage VLAN networks. Additionally specifying a VLAN ID range for
     a physical network enables regular (non-privileged) users to
     manage VLAN networks. The Networking service allocates the VLAN ID
     for each self-service network using the VLAN ID range for the
     physical network.

     .. code-block:: ini

        [ml2_type_vlan]
        ...
        network_vlan_ranges = PHYSICAL_NETWORK:MIN_VLAN_ID:MAX_VLAN_ID

     Replace ``PHYSICAL_NETWORK`` with the physical network name and
     optionally define the minimum and maximum VLAN IDs. Use a comma
     to separate each physical network.

     For example, to enable support for administrative VLAN networks
     on the ``physnet1`` network and self-service VLAN networks on
     the ``physnet2`` network using VLAN IDs 1001 to 2000:

     .. code-block:: ini

        network_vlan_ranges = physnet1,physnet2:1001:2000

   * Enable security groups.

     .. code-block:: ini

        [securitygroup]
        ...
        enable_security_group = true

   * Configure ML2 ODL

     .. code-block:: ini

        [ml2_odl]

        ...
        username = <ODL_USERNAME>
        password = <ODL_PASSWORD>
        url = http://<ODL_IP_ADDRESS>:<ODL_PORT>/controller/nb/v2/neutron
        port_binding_controller = pseudo-agentdb-binding

   * Optionally, To enable ODL DHCP service in an OpenDaylight enabled cloud,
     set `enable_dhcp_service=True` under the `[ml2_odl]` section. It will load
     the openstack-odl-v2-dhcp-driver which will create special DHCP ports in
     neutron for use by the OpenDaylight Controller's DHCP Service. Please make
     sure to set `controller-dhcp-enabled = True` within the OpenDaylight
     Controller configuration file ``netvirt-dhcpservice-config.xml`` along
     with the above configuration.

     `OpenDaylight Spec Documentation Link: <http://docs.opendaylight.org/en/latest/submodules/netvirt/docs/specs/neutron-port-for-dhcp-service.html>`_.

     .. code-block:: ini

        [ml2_odl]

        ...
        enable_dhcp_service = True

Compute/network nodes
---------------------

Each compute/network node runs the OVS services. If compute/network nodes are
already configured to run with Neutron ML2 OVS driver, more steps are
necessary. `OVSDB with OpenStack <http://docs.opendaylight.org/en/latest/
opendaylight-with-openstack/openstack-with-ovsdb.html>`_ can be referred to.

#. Install the ``openvswitch`` packages.

#. Start the OVS service.

   Using the *systemd* unit:

   .. code-block:: console

      # systemctl start openvswitch

   Using the ``ovs-ctl`` script:

   .. code-block:: console

      # /usr/share/openvswitch/scripts/ovs-ctl start

#. Configure OVS to use ODL as a manager.

   .. code-block:: console

      # ovs-vsctl set-manager tcp:${ODL_IP_ADDRESS}:6640

   Replace ``ODL_IP_ADDRESS`` with the IP address of ODL controller node

#. Set host OVS configurations if port_binding_controller is pseudo-agent

   .. code-block:: console

      # sudo neutron-odl-ovs-hostconfig

#. Verify the OVS service.

   .. code-block:: console

      # ovs-vsctl show

.. note::

   After setting config files, you have to restart the neutron server
   if you are using screen then it can be directly started from q-svc
   window or you can use service neutron-server restart, latter may or
   may not work depending on OS you are using.
