==========================================
Quality of Service Driver for OpenDaylight
==========================================

This spec describes the plan to implement quality of service driver for
OpenDaylight Controller.

Problem Statement
=================
OpenStack networking project (neutron [1]) have a extension plugin implemented
and which expose api for quality of service that can be also be implemented by
any backend networking service provider to support QoS. These APIs provide a
way to integrate OpenStack Neutron QoS with any of the backend QoS providers.
OpenDaylight will provide backend for existing functionalities in neutron-QoS.
A notification driver is needed for integration of existing api in Openstack
neutron for QoS with OpenDaylight backend.

Proposed Change
===============
This change will introduce a new notification driver in networking-odl that
will take CRUD requests data for QoS policies from OpenStack neutron and notify
the OpenDaylight controller about the respective operation.

Detailed Design
===============
To enable the formal end to end integration between OpenStack QoS and
OpenDaylight requires an networking-odl QoS notification driver. QoS driver
will act as a shim layer between OpenStack and OpenDaylight that will carry
out following task:

#. After getting QoS policy request data from neutron, It will log a operation
    request in opendaylightjournal table.

#. The operation will be picked from opendaylightjournal table and a rest call
    for notifying OpenDaylight server will be prepared and sent.

#. This request will processed by neutron northbound in OpenDaylight.
The OpenDaylight neutron northbound project. These models will be based
on the existing neutron qos plugin APIs.

QoS providers in OpenDaylight can listen to these OpenDaylight Neutron
Northbound QoS models and translate it to their specific yang models for QoS.
The following diagram shows the high level integration between OpenStack and
the OpenDaylight QoS provider::

                           +---------------------------------------------+
                           | OpenStack Network Server (neutron qos)      |
                           |                                             |
                           |            +---------------------+          |
                           |            | networking-odl      |          |
                           |            |                     |          |
                           |            |     +---------------|          |
                           |            |     | Notification  |          |
                           |            |     | driver QoS    |          |
                           +----------------------|----------------------+
                                                  |
                                                  | Rest Communication
                                                  |
                    OpenDaylight Controller       |
                          +-----------------------|------------+
                          |            +----------V----+       |
                          | ODL        | QoS Yang Model|       |
                          | Northbound |               |       |
                          | (neutron)  +---------------+       |
                          |                    |               |
                          |                    |               |
                          | ODL           +----V----+          |
                          | Southbound    | QoS     |          |
                          | (neutron)     +---------+          |
                          +-----------------|------------------+
                                            |
                                            |
                          +------------------------------------+
                          |           Network/OVS              |
                          |                                    |
                          +------------------------------------+

In the above diagram, the OpenDaylight components are shown just to understand
the overall architecture, but it's out of scope of this spec's work items.
This spec will only track progress related to networking-odl notification QoS
driver work.

Dependencies
============
It has a dependency on OpenDaylight Neutron Northbound QoS yang models, but
that is out of scope of this spec.

Impact
======
None

Assignee(s)
===========

Following developers will be the initial contributor to the driver, but we
will be happy to have more contributor on board.

* Manjeet Singh Bhatia (manjeet.s.bhatia@intel.com, irc: manjeets)

References
==========

* [1] https://docs.openstack.org/neutron/latest/contributor/internals/quality_of_service.html
* [2] https://wiki.opendaylight.org/view/NeutronNorthbound:Main
