#!/usr/bin/env bash

set -ex

VENV=${1:-"dsvm-functional"}

GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack
NETWORKING_ODL_DIR="${NETWORKING_ODL_DIR:-$BASE/new/networking-odl}"

case $VENV in
"dsvm-functional" | "dsvm-fullstack")
    # The following need to be set before sourcing
    # configure_for_func_testing.
    PROJECT_NAME=networking-odl
    IS_GATE=True

    source $NETWORKING_ODL_DIR/tools/configure_for_func_testing.sh
    configure_host_for_func_testing
    ;;
*)
    echo "Unrecognized environment $VENV".
    exit 1
esac
