#Service Function Chaining Driver for OpenDaylight

OpenStack SFC project exposes generic APIs[1] for Service Function Chaining (SFC) that can be implemented by any backend networking service provider to support SFC. These APIs provide a way for integrating OpenStack SFC with any of the backend SFC provider. OpenDaylight SFC project provides a very mature implementation of SFC [2], but currently there is no formal integration mechanism is present to consume OpenDaylight SFC project as a SFC provider for OpenStack SFC. 

Recently Tacker project [3] is been approved as an official project to OpenStack, that opens many possibility to realize the NFV use cases (e.g SFC) using OpenStack as a platform. Providing a formal end to end integration between OpenStack and OpenDaylight for SFC use case will help NFV users to leverage OpenStack, Tacker and OpenDaylight as a solution. This integration work is already been POC [4][5] by Tim Rozets, but in this POC work, Tacker directly communicate to OpenDaylight SFC & classifier providers and not through OpenStack SFC APIs (networking-sfc). 

To enable the formal end to end integration between OpenStack SFC and OpenDaylight, it requires a SFC driver for OpenDaylight. ODL SFC driver will act as a shim layer between OpenStack and OpenDaylight, that will carry out following two main task:

* Translation of OpenStack SFC Classifier API to generic ODL SFC classifier yang models** based on IETF Netmod ACL models [7]
* Translation of OpenStack SFC API's to OpenDaylight SFC API's [8]

** This work is not yet done, but OpenDaylight project need to come up with these generic yang models for SFC classification that can be used by any SFC classifier providers (E.g Net-Virt, GBP ). This work is out of scope of this work and will be collaborated in the scope of OpenDaylight Neutron Northbound project[8].

Following diagram shows the high level integration between OpenStack and OpenDaylight SFC provider.

                            +---------------------------------------------+
                            | OpenStack Network Server                    |
                            |            +-------------------+            |
                            |            | networking-odl    |            |
                            |            |   SFC Driver      |            |
                            |            +-------------------+            |
                            +----------------------|----------------------+
                                                   |
                                                   |
                                         -----------------------
                OpenDaylight Controller |                       |
                +-----------------------|-----------------------|---------------+
                |            +----------v----+              +---v---+           |
                | Neutron    | SFC Classifier|              |SFC    | SFC       |
                | Northbound |    Models     |              |Models | Project   |
                | Project    +---------------+              +-------+           |
                |               /        \                      |               |
                |             /           \                     |               |
                |           /               \                   |               |
                |     +-----V--+        +---V----+              |               |
                |     |Net-Virt|  ...   |   GBP  |              |               |
                |     +---------+       +--------+              |               |
                +-----------|----------------|------------------|---------------+
                            |                |                  |
                            |                |                  |
                +-----------V----------------V------------------V---------------+
                |                     Network/OVS                               |
                |                                                               |
                +---------------------------------------------------------------+

In the above architecture, opendaylight components are shown just to understand the overall architecture, but it's out of scope of this blueprint's work items. This blue print only will track progress related to networking-odl OpenStack sfc driver work.

Given that OpenStack SFC APIs are port-pair based API's and OpenDaylight SFC API's are based on IETF SFC yang models[7], there might be situation where translation might requires API enhancement from OpenStack SFC. Networking SFC team is open for these new enhancement requirements given that those are generic enough to be leveraged by other backend SFC providers[8]. This work will be leveraging the POC work done by Tim [9] to come up with the first version of SFC driver.

##Assignee(s)

Following developers will be the initial contributor to the driver, but we will be happy to have more contributor on board.

* Anil Vishnoi (vishnoianil@gmail.com, irc: vishnoianil)
* Tim Rozets (trozet@redhat.com, irc: trozet)

##References

[1] https://github.com/openstack/networking-sfc/blob/master/doc/source/api.rst

[2] https://wiki.opendaylight.org/view/Service_Function_Chaining:Main

[3] https://wiki.openstack.org/wiki/Tacker

[4] https://github.com/trozet/tacker/tree/SFC_brahmaputra/tacker/sfc

[5] https://github.com/trozet/tacker/tree/SFC_brahmaputra/tacker/sfc_classifier

[6] https://tools.ietf.org/html/draft-ietf-netmod-acl-model-05

[7] https://github.com/opendaylight/sfc/tree/master/sfc-model/src/main/yang

[8] http://eavesdrop.openstack.org/meetings/service_chaining/2016/service_chaining.2016-03-31-17.00.log.html

[9] https://github.com/trozet/tacker/blob/SFC_brahmaputra/tacker/sfc/drivers/opendaylight.py
