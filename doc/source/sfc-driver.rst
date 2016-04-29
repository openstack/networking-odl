=================================================
Service Function Chaining Driver for OpenDaylight
=================================================

This spec describes the plan to implement OpenStack networking-sfc[1] driver for OpenDaylight
Controller.

Problem Statement
===================
OpenStack SFC project (networking-sfc [1]) exposes generic APIs[2] for Service Function Chaining
(SFC) that can be implemented by any backend networking service provider to support SFC. These APIs
provide a way to integrate OpenStack SFC with any of the backend SFC providers. OpenDaylight SFC
project provides a very mature implementation of SFC [3], but currently there is no formal
integration mechanism present to consume OpenDaylight as an SFC provider for networking-sfc.

Recently Tacker project [4] has been approved as an official project in OpenStack, that opens many
possibilities to realize the NFV use cases (e.g SFC) using OpenStack as a platform. Providing a
formal end to end integration between OpenStack and OpenDaylight for SFC use case will help NFV
users leverage OpenStack, Tacker and OpenDaylight as a solution. A POC for this integration work has
already been implemented [5][6] by Tim Rozet, but in this POC work, Tacker directly communicates
to OpenDaylight SFC & classifier providers and not through OpenStack SFC APIs (networking-sfc).

Proposed Change
===============
Implementation of this spec will introduce a networking-sfc[1] driver for OpenDaylight Controller in
networking-odl project that will pass through the networking-sfc API's call to the OpenDaylight
Controller.

Detailed Design
===============
To enable the formal end to end integration between OpenStack SFC and OpenDaylight requires an
SFC driver for OpenDaylight. ODL SFC driver will act as a shim layer between OpenStack and
OpenDaylight that will carry out following two main tasks:

* Translation of OpenStack SFC Classifier API to ODL SFC classifier yang models**

* Translation of OpenStack SFC API's to OpenDaylight Neutron Northbound SFC models** [8]

** This work is not yet done, but the OpenDaylight neutron northbound project needs to come up with
yang models for SFC classification/chain. These models will be based on the existing networking-sfc
APIs. This work is out of scope of networking-odl work and will be collaborated in the scope of the
OpenDaylight Neutron Northbound project.

SFC providers (E.g Net-Virt, GBP, SFC ) in OpenDaylight can listen to these OpenDaylight Neutron
Northbound SFC models and translate it to their specific yang models for classification/sfc. The
following diagram shows the high level integration between OpenStack and the OpenDaylight SFC
provider::

                            +---------------------------------------------+
                            | OpenStack Network Server (networking-sfc)   |
                            |            +-------------------+            |
                            |            | networking-odl    |            |
                            |            |   SFC Driver      |            |
                            |            +-------------------+            |
                            +----------------------|----------------------+
                                                   | REST Communication
                                                   |
                                         -----------------------
                OpenDaylight Controller |                       |
                +-----------------------|-----------------------|---------------+
                |            +----------v----+              +---v---+           |
                | Neutron    | SFC Classifier|              |SFC    | Neutron   |
                | Northbound |    Models     |              |Models | Northbound|
                | Project    +---------------+              +-------+ Project   |
                |               /        \                      |               |
                |             /           \                     |               |
                |           /               \                   |               |
                |     +-----V--+        +---V----+          +---V---+           |
                |     |Net-Virt|  ...   |   GBP  |          |  SFC  |  ...      |
                |     +---------+       +--------+          +-------+           |
                +-----------|----------------|------------------|---------------+
                            |                |                  |
                            |                |                  |
                +-----------V----------------V------------------V---------------+
                |                     Network/OVS                               |
                |                                                               |
                +---------------------------------------------------------------+

In the above architecture, the opendaylight components are shown just to understand the overall
architecture, but it's out of scope of this spec's work items. This spec will only track
progress related to networking-odl OpenStack sfc driver work.

Given that OpenStack SFC APIs are port-pair based API's and OpenDaylight SFC API's are based on
IETF SFC yang models[8], there might be situations where translation might requires API enhancement
from OpenStack SFC. Networking SFC team is open for these new enhancement requirements given that
they are generic enough to be leveraged by other backend SFC providers[9]. This work will be
leveraging the POC work done by Tim [10] to come up with the first version of SFC driver.

Dependencies
============
It has a dependency on OpenDaylight Neutron Northbound SFC classifier and chain yang models, but
that is out of scope of this spec.

Impact
======
None

Assignee(s)
===========

Following developers will be the initial contributor to the driver, but we will be happy to have
more contributor on board.

* Anil Vishnoi (vishnoianil@gmail.com, irc: vishnoianil)
* Tim Rozet (trozet@redhat.com, irc: trozet)

References
==========

[1] http://docs.openstack.org/developer/networking-sfc/

[2] https://github.com/openstack/networking-sfc/blob/master/doc/source/api.rst

[3] https://wiki.opendaylight.org/view/Service_Function_Chaining:Main

[4] https://wiki.openstack.org/wiki/Tacker

[5] https://github.com/trozet/tacker/tree/SFC_brahmaputra/tacker/sfc

[6] https://github.com/trozet/tacker/tree/SFC_brahmaputra/tacker/sfc_classifier

[7] https://tools.ietf.org/html/draft-ietf-netmod-acl-model-05

[8] https://wiki.opendaylight.org/view/NeutronNorthbound:Main

[9] http://eavesdrop.openstack.org/meetings/service_chaining/2016/service_chaining.2016-03-31-17.00.log.html

[10] https://github.com/trozet/tacker/blob/SFC_brahmaputra/tacker/sfc/drivers/opendaylight.py
