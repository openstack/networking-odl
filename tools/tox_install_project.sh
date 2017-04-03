#!/usr/bin/env bash

# Many of neutron's repos suffer from the problem of depending on neutron,
# but it not existing on pypi.

# This wrapper for tox's package installer will use
# the local tree in home directory if exists,
# else the existing package if it exists,
# else use zuul-cloner if that program exists,
# else grab it from project master via https://git.openstack.org/openstack,
# That last case should only happen with devs running unit tests locally.

# From the tox.ini config page:
# install_command=ARGV
# default:
# pip install {opts} {packages}

PROJ=$1
MOD=$2
shift 2

ZUUL_CLONER=/usr/zuul-env/bin/zuul-cloner
neutron_installed=$(echo "import ${MOD}" | python 2>/dev/null ; echo $?)
BRANCH_NAME=master
NEUTRON_DIR=$HOME/${PROJ}

set -e
set -x

CONSTRAINTS_FILE=$1
shift

install_cmd="pip install"
if [ $CONSTRAINTS_FILE != "unconstrained" ]; then
    install_cmd="$install_cmd -c$CONSTRAINTS_FILE"
fi

# The devstack based functional tests have neutron checked out in
# $NEUTRON_DIR on the test systems - with the change to test in it.
# Use this directory if it exists, so that this script installs the
# neutron version to test here.
# Note that the functional tests use sudo to run tox and thus
# variables used for zuul-cloner to check out the correct version are
# lost.
if [ -d "$NEUTRON_DIR" ]; then
    echo "FOUND ${PROJ} code at $NEUTRON_DIR - using"
    $install_cmd -U -e $NEUTRON_DIR
elif [ $neutron_installed -eq 0 ]; then
    echo "ALREADY INSTALLED" > /tmp/tox_install-${PROJ}.txt
    location=$(python -c "import ${MOD}; print(${MOD}.__file__)")
    echo "ALREADY INSTALLED at $location"

    echo "${PROJ} already installed; using existing package"
elif [ -x "$ZUUL_CLONER" ]; then
    echo "ZUUL CLONER" > /tmp/tox_install-${PROJ}.txt
    # Make this relative to current working directory so that
    # git clean can remove it. We cannot remove the directory directly
    # since it is referenced after $install_cmd -e.
    mkdir -p .tmp
    PROJECT_DIR=$(/bin/mktemp -d -p $(pwd)/.tmp)
    pushd $PROJECT_DIR
    $ZUUL_CLONER --cache-dir \
        /opt/git \
        --branch ${BRANCH_NAME} \
        git://git.openstack.org \
        openstack/${PROJ}
    cd openstack/${PROJ}
    $install_cmd -e .
    popd
else
    echo "PIP HARDCODE" > /tmp/tox_install-${PROJ}.txt
    $install_cmd -U -egit+https://git.openstack.org/openstack/${PROJ}@${BRANCH_NAME}#egg=${PROJ}
fi
