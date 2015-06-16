#!/usr/bin/env bash

set -xe

# Be explicit about what services we enable
ENABLED_SERVICES=q-svc,q-dhcp,q-meta,quantum,tempest,
ENABLED_SERVICES+=n-api,n-cond,n-cpu,n-crt,n-obj,n-sch
ENABLED_SERVICES+=g-api,g-reg,mysql,rabbit,key

export ENABLED_SERVICES

# For now, run a small number of tests until we get the issues
# on the ODL sorted out
export DEVSTACK_GATE_TEMPEST_REGEX="tempest.api.network.test_networks \
                                    tempest.api.network.test_networks_negative \
                                    tempest.api.network.test_ports"
