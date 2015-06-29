#!/usr/bin/env bash

set -xe

GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

TEMPEST_DIR="$BASE/new/tempest"
NETWORKING_ODL_DIR="$BASE/new/networking-odl"

source $DEVSTACK_PATH/functions
source $DEVSTACK_PATH/localrc

IS_GATE=$(trueorfalse True IS_GATE)
if [[ "$IS_GATE" == "True" ]]
then
    source $NETWORKING_ODL_DIR/devstack/devstackgaterc
fi

owner=stack
sudo_env="TEMPEST_CONFIG_DIR=$TEMPEST_DIR/etc"

cd $TEMPEST_DIR
sudo chown -R $owner:stack $TEMPEST_DIR

echo "Running networking-odl test suite"
sudo -H -u $owner $sudo_env tools/pretty_tox.sh "$DEVSTACK_GATE_TEMPEST_REGEX"
