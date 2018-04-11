#!/usr/bin/env bash

set -e
set -x

DIR=$(dirname $0)
${DIR}/tox_install_project.sh ceilometer ceilometer $*
${DIR}/tox_install_project.sh neutron neutron $*
${DIR}/tox_install_project.sh neutron-lbaas neutron_lbaas $*
${DIR}/tox_install_project.sh networking-l2gw networking_l2gw $*
${DIR}/tox_install_project.sh networking-sfc networking_sfc $*
${DIR}/tox_install_project.sh networking-bgpvpn networking_bgpvpn $*
CONSTRAINTS_FILE=$1
shift

install_cmd="pip install"
if [ $CONSTRAINTS_FILE != "unconstrained" ]; then
    install_cmd="$install_cmd -c$CONSTRAINTS_FILE"
fi

if [ -z "$*" ]; then
    echo "No packages to be installed."
    exit 0
fi

$install_cmd -U $*
exit $?
