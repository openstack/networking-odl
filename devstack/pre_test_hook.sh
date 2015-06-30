#!/usr/bin/env bash

set -xe

# Drop a token that marks the build as coming from openstack infra
GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack
echo "IS_GATE=True" >> $DEVSTACK_PATH/localrc

# Set here the ODL release to use for the Gate job
echo "ODL_RELEASE=lithium-snapshot-0.3.1" >> $DEVSTACK_PATH/localrc
