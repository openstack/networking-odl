#!/usr/bin/env bash

set -xe

NETWORKING_ODL_DIR="$BASE/new/networking-odl"
TEMPEST_DIR="$BASE/new/tempest"
SCRIPTS_DIR="/usr/local/jenkins/slave_scripts"

# For now, run a small number of tests until we get the issues
# on the ODL sorted out
export DEVSTACK_GATE_TEMPEST_REGEX="tempest.api.network.test_networks \
                                    tempest.api.network.test_networks_negative \
                                    tempest.api.network.test_ports \
                                    tempest.api.network.test_floating_ips \
                                    tempest.api.network.test_floating_ips_negative"

owner=stack
sudo_env="TEMPEST_CONFIG_DIR=$TEMPEST_DIR/etc"

cd $TEMPEST_DIR
sudo chown -R $owner:stack $TEMPEST_DIR

echo "Running networking-odl test suite"
sudo -H -u $owner $sudo_env tools/pretty_tox.sh "$DEVSTACK_GATE_TEMPEST_REGEX"
