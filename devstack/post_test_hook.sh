#!/usr/bin/env bash

set -xe

GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

source $DEVSTACK_PATH/functions
source $DEVSTACK_PATH/localrc

TEMPEST_CODE_DIR="$BASE/new/tempest"
TEMPEST_DATA_DIR="$DATA_DIR/tempest"
NETWORKING_ODL_DIR="$BASE/new/networking-odl"

sudo ip address
sudo ip link
sudo ip route

owner=stack
sudo_env="TEMPEST_CONFIG_DIR=$TEMPEST_CODE_DIR/etc"

cd $TEMPEST_CODE_DIR
sudo chown -R $owner:stack $TEMPEST_CODE_DIR
sudo mkdir -p "$TEMPEST_DATA_DIR"
sudo chown -R $owner:stack $TEMPEST_DATA_DIR
source $DEVSTACK_PATH/openrc admin admin

echo "Some pre-process info"
neutron net-list
neutron port-list
neutron subnet-list
neutron router-list

echo "Running networking-odl test suite"
sudo -H -u $owner $sudo_env tox -eall -- "$DEVSTACK_GATE_TEMPEST_REGEX" --serial

echo "Some post-process info"
neutron net-list
neutron port-list
neutron subnet-list
neutron router-list
