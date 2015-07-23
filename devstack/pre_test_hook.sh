#!/usr/bin/env bash

set -xe

# Drop a token that marks the build as coming from openstack infra
GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

cat <<EOF >> $DEVSTACK_PATH/localrc

IS_GATE=True

# Set here the ODL release to use for the Gate job
ODL_RELEASE=lithium-snapshot-0.3.1

# Switch to using the ODL's L3 implementation
ODL_L3=True

# Enable debug logs for odl ovsdb
ODL_NETVIRT_DEBUG_LOGS=True

EOF
