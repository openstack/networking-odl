..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

======================================================================
Neutron Port Allocation per Subnet for OpenDaylight DHCP Proxy Service
======================================================================

This spec describes the proposal to allocate a Neutron DHCP Port just for
use by OpenDaylight Controller on Subnets that are created or updated with
enable-dhcp to True.

When in OpenDaylight controller, the "controller-dhcp-enabled" configuration
flag is set to true, these Neutron DHCP Ports will be used by the OpenDaylight
Controller to provide DHCP Service instead of using the subnet-gateway-ip as
the DHCP Server IP as it stands today.

The networking-odl driver is not aware about the above OpenDaylight controller
parameter configuration. When controller-dhcp-enabled configuration flag is set
to false the DHCP port will be created and destroyed without causing any harm
to either OpenDaylight controller or networking-odl driver.

Problem Statement
=================

The DHCP service within OpenDaylight currently assumes availability of the
subnet gateway IP address. The subnet gateway ip is not a mandatory parameter
for an OpenStack subnet, and so it might not be available from OpenStack
orchestration.  This renders the DHCP service in OpenDaylight to not be
able to serve DHCP offers to virtual endpoints requesting for IP addresses,
thereby resulting in service unavailability. Even if subnet-gateway-ip is
available in the subnet, it is not a good design in OpenDaylight to hijack
that ip address and use that as the DHCP Server IP Address.

Problem - 1: L2 Deployment with 3PP gateway
-------------------------------------------

There can be deployment scenario in which L2 network is created with no
distributed Router/VPN functionality. This deployment can have a separate
gateway for the network such as a 3PP LB VM, which acts as a TCP termination
point and this LB VM is configured with a default gateway IP. It means all
inter-subnet traffic is terminated on this VM which takes the responsibility
of forwarding the traffic.

But the current DHCP service in OpenDaylight controller hijacks gateway IP
address for serving DHCP discover/request messages. If the LB is up, this can
continue to work, DHCP broadcasts will get hijacked by the OpenDaylight, and
responses sent as PKT_OUTs with SIP = GW IP.

However, if the LB is down, and the VM ARPs for the same IP as part of a DHCP
renew workflow, the ARP resolution can fail, due to which renew request will
not be generated. This can cause the DHCP lease to lapse.

Problem - 2: Designated DHCP for SR-IOV VMs via HWVTEP
------------------------------------------------------

In this Deployment scenario, L2 network is created with no distributed Router/
VPN functionality, and HWVTEP for SR-IOV VMs. DHCP flood requests from SR-IOV
VMs(DHCP discover, request during bootup), are flooded by the HWVTEP on the
L2 Broadcast domain, and punted to the controller by designated vswitch. DHCP
offers are sent as unicast responses from Controller, which are forwarded by
the HWVTEP to the VM. DHCP renews can be unicast requests, which the HWVTEP
may forward to an external Gateway VM (3PPLB VM) as unicast packets. Designated
vswitch will never receive these pkts, and thus not be able to punt them to the
controller, so renews will fail.

Proposed Change
===============
In general as part of implementation of this spec, we are introducing a new
configuration parameter 'create_opendaylight_dhcp_port' whose truth value
determines whether the dhcp-proxy-service within the openstack-odl framework
need to be made functional. This service will be responsible for managing the
create/update/delete lifecycle for a new set of Neutron DHCP Ports which will
be provisioned specifically for use by the OpenDaylight Controller's existing
DHCP Service Module.

Detailed Design
===============
Introduce a driver config parameter(create_opendaylight_dhcp_port) to determine
if OpenDaylight based DHCP service is being used. Default setting for the
parameter is false.

When 'create_opendaylight_dhcp_port' is set to True, it triggers the networking
-odl ml2 driver to hook on to OpenStack subnet resource lifecycle and use that
to manage a special DHCP port per subnet for OpenDaylight Controller use. These
special DHCP ports will be shipped to OpenDaylight controller, so that DHCP
Service within the OpenDaylight controller can make use of these as DHCP
Server ports themselves. The port will be used to service DHCP requests for
virtual end points belonging to that subnet.

These special DHCP Ports (one per subnet), will carry unique device-id and
device-owner values.

* device-owner(network:dhcp)
* device-id(OpenDaylight-<subnet-id>)

OpenDaylight DHCP service will also introduce a new config parameter controller
-dhcp-mode to indicate if the above DHCP port should be used for servicing DHCP
requests. When the parameter is set to use-odl-dhcp-neutron-port, it is
recommended to enable the create_opendaylight_dhcp_port flag for the networking
-odl driver.

Alternative 1
--------------
The creation of Neutron OpenDaylight DHCP port will be invoked within the
OpenDaylight mechanism Driver subnet-postcommit execution.

Any failures during the neutron dhcp port creation or allocation for the subnet
should trigger failure of the subnet create operation with an appropriate
failure message in logs. On success the subnet and port information will be
persisted to Journal DB and will subsequently synced with the OpenDaylight
controller.

The plugin should initiate the removal of allocated dhcp neutron port at the
time of subnet delete. The port removal will be handled in a subnet-delete-
post-commit execution and any failure during this process should rollback the
subnet delete operation. The subnet delete operation will be allowed only when
all other VMs launched on this subnet are already removed as per existing
Neutron behavior.

A subnet update operation configuring the DHCP state as enabled should allocate
such a port if not previously allocated for the subnet. Similarly a subnet
update operation configuring DHCP state to disabled should remove any
previously allocated OpenDaylight DHCP neutron ports.

Since the invocation of create/delete port will be synchronous within subnet
post-commit, a failure to create/delete port will result in an exception being
thrown which makes the ML2 Plugin to fail the subnet operation and not alter
Openstack DB.

Alternative 2
-------------
The OpenDaylight Neutron DHCP Port creation/deletion is invoked asyncronously
driven by a journal entry callback for any Subnet resource state changes as
part of create/update/delete. A generic journal callback mechanism to be
implemented. Initial consumer of this callback would be the OpenDaylight
DHCP proxy service but this could be used by other services in future.

The Neutron DHCP Port (for OpenDaylight use) creation is triggered when the
subnet journal-entry is moved from PENDING to PROCESSING. On a failure of
port-creation, the journal will be retained in PENDING state and the subnet
itself won't be synced to the OpenDaylight controller. The journal-entry state
is marked as COMPLETED only on successful port creation and successful
synchronization of that subnet resource to OpenDaylight controller. The same
behavior is applicable for subnet update and delete operations too.

The subnet create/update operation that allocates an OpenDaylight DHCP port
to always check if a port exists and allocate new port only if none exists
for the subnet.

Since the invocation of create/delete port will be within the journal callback
and asynchronous to subnet-postcommit, the failure to create/delete port
will result in the created (or updated) subnet to remain in PENDING state. Next
journal sync of this pending subnet will again retry creation/deletion of port
and this cycle will happen until either create/delete port succeeds or the
subnet is itself deleted by the orchestrating tenant. This could result in
piling up of journal PENDING entries for these subnets when there is an
unexpected failure in create/delete DHCP port operation. It is recommended to
not keep retrying the port operation and  instead failures would be indicated
in OpenDaylight as DHCP offers/renews will not be honored by the dhcp service
within the OpenDaylight controller, for that subnet.

Recommended Alternative
-----------------------

All of the following cases will need to be addressed by the design.

* Neutron server can crash after submitting information to DB but before
  invoking post-commit during a subnet create/update/delete operation. The
  dhcp-proxy-service should handle the DHCP port creation/deletion during
  such failures when the service is enabled.
* A subnet update operation to disable-dhcp can be immediately followed by
  a subnet update operation to enable-dhcp, and such a situation should end up
  in creating the neutron-dhcp-port for consumption by OpenDaylight.
* A subnet update operation to enable-dhcp can be immediately followed by a
  subnet update operation to disable-dhcp, and such a situation should end up
  in deleting the neutron-dhcp-port that was created for use by OpenDaylight.
* A subnet update operation to enable-dhcp can be immediately followed by a
  subnet delete operation,and such a situation should end up deleting the
  neutron-dhcp-port that was about to be provided for use by OpenDaylight.
* A subnet create operation (with dhcp enabled) can be immediately followed
  by a subnet update operation to disable-dhcp, and such a situation should
  end up in deleting the neutron-dhcp-port that was created for use by
  OpenDaylight.

Design as per Alternative 2 meets the above cases better and is what we propose
to take as the approach that we will pursue for this spec.

Dependencies
============
Feature is dependent on enhancement in OpenDaylight DHCP Service as per the
Spec in [1]

Impact
======
None

Assignee(s)
===========

* Achuth Maniyedath (achuth.m@altencalsoftlabs.com)
* Karthik Prasad(karthik.p@altencalsoftlabs.com)

References
==========

* [1] OpenDaylight spec to cover this feature
  https://git.opendaylight.org/gerrit/#/c/52298/
