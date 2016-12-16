#! /bin/bash
#
# override configurations of reproduce.sh
#

export NETWORKING_ODL_DIR=/home/vagrant/networking-odl

# Adjust path to scripts in networking-odl
pre_test_hook ()
{
    . $NETWORKING_ODL_DIR/devstack/pre_test_hook.sh
}
declare -fx pre_test_hook
gate_hook ()
{
    bash -xe $NETWORKING_ODL_DIR/networking_odl/tests/contrib/gate_hook.sh dsvm-functional
}
declare -fx gate_hook
post_test_hook ()
{
    # Don't run tests.
    sudo chown -R stack:stack $BASE/new
    # sudo -H -u stack tox -e dsvm-function

    # bash -xe $NETWORKING_ODL_DIR/networking_odl/tests/contrib/post_test_hook.sh dsvm-functional dsvm-functional
}
declare -fx post_test_hook

# we don't need most of projects. networking-odl isn't needed.
export DEVSTACK_LOCAL_CONFIG=""
export DEVSTACK_GATE_SETTINGS="$NETWORKING_ODL_DIR/devstack/devstackgaterc"
export PROJECTS=""
export OVERRIDE_ENABLED_SERVICES="odl-server"
export DEVSTACK_GATE_PROJECTS_OVERRIDE
DEVSTACK_GATE_PROJECTS_OVERRIDE="openstack-infra/devstack-gate"
DEVSTACK_GATE_PROJECTS_OVERRIDE="openstack-dev/devstack $DEVSTACK_GATE_PROJECTS_OVERRIDE"
DEVSTACK_GATE_PROJECTS_OVERRIDE="openstack/requirements $DEVSTACK_GATE_PROJECTS_OVERRIDE"
export ODL_RELEASE_BASE=carbon-snapshot
