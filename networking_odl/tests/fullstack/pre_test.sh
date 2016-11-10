#!/bin/bash
# During unstacking, neutron will delete br-int, so get it back

sudo ovs-vsctl br-exists br-int
if [[ $? = 0 ]]; then
    exit 0
fi

sudo ovs-vsctl add-br br-int -- set-controller br-int  tcp:127.0.0.1:6653
