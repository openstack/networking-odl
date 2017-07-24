Reference Architecture
======================
This document lists the minimum reference architecture to get OpenStack
installed with OpenDayLight. Wherever possible, additional resources will be
stated.

Cloud Composition
-----------------
The basic cloud will have 3 types of nodes:

* Controller Node - Runs OpenStack services and the ODL controller.
* Network Node - Runs the DHCP agent, the metadata agent, and the L3 agent (for
  SNAT).
* Compute Node - VMs live here.

Usually each of the first 2 types of nodes will have a cluster of 3 nodes to
support HA. It's also possible to run the ODL controller on separate hardware
than the OpenStack services, but this isn't mandatory.

The last type of nodes can have as many nodes as scale requirements dictate.

Networking Requirements
-----------------------
There are several types of networks on the cloud, the most important for the
reference architecture are:

* Management Network - This is the network used to communicate between the
  different management components, i.e. Nova controller to Nova agent, Neutron
  to ODL, ODL to OVS, etc.
* External Network - This network provides VMs with external connectivity (i.e.
  internet) usually via virtual routers.
* Data Network - This is the network used to connect the VMs to each other and
  to network resources such as virtual routers.

The Control Nodes usually are only connected to the Management Network, unless
they have an externally reachable IP on the External Network.

The other node types are connected to all the networks since ODL uses a
distributed routing model so that each Compute Node hosts a "virtual router"
responsible for connecting the VMs from that node to other networks (including
the External Network).

This diagram illustrates how these nodes might be connected::

              Controller Node
             +-----------------+
             |                 |
   +-----------+192.168.0.251  |
   |         |                 |
   |         +-----------------+
   |
   |          Compute Node      +----------------+
   |         +---------------+  | Legend         |
   |         |               |  +----------------+
   +-----------+192.168.0.1  |  |                |
   |         |               |  | --- Management |
   | +~~~~~~~~~+10.0.0.1     |  |                |
   | |       |               |  | ~~~ Data       |
   | | +=======+br-int       |  |                |
   | | |     |               |  | === External   |
   | | |     +---------------+  |                |
   | | |                        +----------------+
   | | |      Network Node
   | | |     +-----------------+
   | | |     |                 |
   +-----------+192.168.0.100  |
     | |     |                 |
     +~~~~~~~~~+10.0.0.100     |
       |     |                 |
       |=======+br-int         |
       |     |                 |
       |     +-----------------+
  +----+---+
  |        |
  | Router |
  |        |
  +--------+


Minimal Hardware Requirements
-----------------------------
The rule of thumb is the bigger the better, more RAM and more cores will
translate to a better environment. For a POC environment the following is
necessary:

Management Node
~~~~~~~~~~~~~~~
CPU: 2 cores

Memory: 8 GB

Storage: 100 GB

Network: 1 * 1 Gbps NIC

Network Node
~~~~~~~~~~~~
CPU: 2 cores

Memory: 2 GB

Storage: 50 GB

Network: 1 Gbps NIC (Management Network), 2 * 1+ Gbps NICs


Compute Node
~~~~~~~~~~~~
CPU: 2+ cores

Memory: 8+ GB

Storage: 100 GB

Network: 1 Gbps NIC (Management Network), 2 * 1+ Gbps NICs

