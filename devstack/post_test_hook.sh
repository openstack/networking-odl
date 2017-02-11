#!/usr/bin/env bash

set -xe

GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

source $DEVSTACK_PATH/functions
source $DEVSTACK_PATH/openrc admin admin

TEMPEST_CODE_DIR="$BASE/new/tempest"
TEMPEST_DATA_DIR="$DATA_DIR/tempest"
NETWORKING_ODL_DIR="${NETWORKING_ODL_DIR:-$BASE/new/networking-odl}"

owner=stack
sudo_env="TEMPEST_CONFIG_DIR=$TEMPEST_CODE_DIR/etc"

cd $TEMPEST_CODE_DIR
sudo chown -R $owner:stack $TEMPEST_CODE_DIR
sudo mkdir -p "$TEMPEST_DATA_DIR"
sudo chown -R $owner:stack $TEMPEST_DATA_DIR

function _odl_show_info {
    sudo ip address
    sudo ip link
    sudo ip route
    sudo ovsdb-client dump
    sudo ovs-vsctl show
    for br in $(sudo ovs-vsctl list-br)
    do
        echo "--- flows on $br ---"
        sudo ovs-ofctl --protocols OpenFlow13 dump-ports $br
        sudo ovs-ofctl --protocols OpenFlow13 dump-ports-desc $br
        sudo ovs-ofctl --protocols OpenFlow13 dump-flows $br
    done

    neutron net-list
    neutron port-list
    neutron subnet-list
    neutron router-list

    # ODL_UESRNAME=admin
    # ODL_PASSWORD=admin
    # ODL_MGR_IP=$SERVICE_HOST
    # ODL_PORT=8087
    # There is no good way to retrieve from setting.odl at the moment
    curl --silent --user admin:admin "http://localhost:8087/restconf/config/neutron:neutron?prettyPrint=true"
    echo -e "\n"
}

echo "Some pre-process info"
_odl_show_info

echo "Running networking-odl test suite"
set +e
sudo -H -u $owner $sudo_env tox -eall -- "$DEVSTACK_GATE_TEMPEST_REGEX" --serial
retval=$?
set -e

echo "Some post-process info"
_odl_show_info

return $retval
