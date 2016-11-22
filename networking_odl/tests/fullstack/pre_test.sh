#!/bin/bash
# During unstacking, neutron will delete br-int, so get it back

sudo -n ovs-vsctl --may-exist add-br br-int -- set-controller br-int  tcp:127.0.0.1:6653
