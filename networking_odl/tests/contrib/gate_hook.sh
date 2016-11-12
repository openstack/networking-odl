#!/usr/bin/env bash

set -ex

VENV=${1:-"dsvm-functional"}

GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack
GATE_STACK_USER=stack
NETWORKING_ODL_PATH="$BASE/new/networking-odl"

case $VENV in
"dsvm-functional")
    # The following need to be set before sourcing
    # configure_for_func_testing.
    PROJECT_NAME=networking-odl
    IS_GATE=True

    sudo chown -R $STACK_USER:$STACK_USER $BASE

    source $DEVSTACK_PATH/functions

    source $NETWORKING_ODL_PATH/tools/configure_for_func_testing.sh

    configure_host_for_func_testing

    # Make the workspace owned by the stack user
    sudo chown -R $STACK_USER:$STACK_USER $BASE
    ;;
"dsvm-fullstack")
    # Fullstack testing happens in post-test-hook.sh
    # Make the workspace owned by GATE_STACK_USER
    sudo chown -R $GATE_STACK_USER:$GATE_STACK_USER $BASE
    ;;
*)
    echo "Unrecognized environment $VENV".
    exit 1
esac
