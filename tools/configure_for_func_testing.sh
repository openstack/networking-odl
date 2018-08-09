#!/usr/bin/env bash

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


set -e


# Control variable used to determine whether to execute this script
# directly or allow the gate_hook to import.
IS_GATE=${IS_GATE:-False}
USE_CONSTRAINT_ENV=${USE_CONSTRAINT_ENV:-True}


if [[ "$IS_GATE" != "True" ]] && [[ "$#" -lt 1 ]]; then
    >&2 echo "Usage: $0 /path/to/devstack [-i]
Configure a host to run Networking ODL's functional test suite.

-i  Install Networking ODL's package dependencies.  By default, it is assumed
    that devstack has already been used to deploy Networking ODL to the
    target host and that package dependencies need not be installed.

Warning: This script relies on devstack to perform extensive
modification to the underlying host.  It is recommended that it be
invoked only on a throw-away VM."
    exit 1
fi


# Skip the first argument
OPTIND=2
while getopts ":i" opt; do
    case $opt in
        i)
            INSTALL_BASE_DEPENDENCIES=True
            ;;
    esac

done

# Default to environment variables to permit the gate_hook to override
# when sourcing.
VENV=${VENV:-dsvm-functional}
DEVSTACK_PATH=${DEVSTACK_PATH:-$(cd "$1" && pwd)}
PROJECT_NAME=${PROJECT_NAME:-networking-odl}
REPO_BASE=${GATE_DEST:-$(cd $(dirname "$0")/../.. && pwd)}
INSTALL_MYSQL_ONLY=${INSTALL_MYSQL_ONLY:-False}
# The gate should automatically install dependencies.
INSTALL_BASE_DEPENDENCIES=${INSTALL_BASE_DEPENDENCIES:-$IS_GATE}
ODL_DIR=$GATE_DEST/opendaylight

if [ ! -f "$DEVSTACK_PATH/stack.sh" ]; then
    >&2 echo "Unable to find devstack at '$DEVSTACK_PATH'.  Please verify that the specified path points to a valid devstack repo."
    exit 1
fi


set -x


function _init {
    # Subsequently-called devstack functions depend on the following variables.
    HOST_IP=127.0.0.1
    FILES=$DEVSTACK_PATH/files
    TOP_DIR=$DEVSTACK_PATH

    source $DEVSTACK_PATH/inc/meta-config
    extract_localrc_section $TOP_DIR/local.conf $TOP_DIR/localrc $TOP_DIR/.localrc.auto
    source $DEVSTACK_PATH/stackrc

    # Allow the gate to override values set by stackrc.
    DEST=${GATE_DEST:-$DEST}
    STACK_USER=${GATE_STACK_USER:-$STACK_USER}
    REQUIREMENTS_DIR=$DEST/requirements
}


function _install_base_deps {
    echo_summary "Installing base dependencies"

    INSTALL_TESTONLY_PACKAGES=True
    PACKAGES=$(get_packages general)
    # for gethostip command
    if ! is_plugin_enabled networking-odl; then
        enable_plugin networking-odl https://git.openstack.org/openstack/networking-odl
    fi
    PACKAGES="$PACKAGES $(get_plugin_packages)"
    # Do not install 'python-' prefixed packages other than
    # python-dev*. Networking ODL's functional testing relies on deployment
    # to a tox env so there is no point in installing python
    # dependencies system-wide.
    PACKAGES=$(echo $PACKAGES | perl -pe 's|python-(?!dev)[^ ]*||g')
    install_package $PACKAGES
}


# _install_databases [install_pg]
function _install_databases {
    local install_pg=${1:-True}

    echo_summary "Installing databases"

    # Avoid attempting to configure the db if it appears to already
    # have run.  The setup as currently defined is not idempotent.
    if mysql openstack_citest > /dev/null 2>&1 < /dev/null; then
        echo_summary "DB config appears to be complete, skipping."
        return 0
    fi

    MYSQL_PASSWORD=${MYSQL_PASSWORD:-secretmysql}
    DATABASE_PASSWORD=${DATABASE_PASSWORD:-secretdatabase}

    source $DEVSTACK_PATH/lib/database

    enable_service mysql
    initialize_database_backends
    install_database
    configure_database_mysql

    if [[ "$install_pg" == "True" ]]; then
        # acl package includes setfacl.
        install_package acl
        enable_service postgresql
        initialize_database_backends
        install_database
        configure_database_postgresql
    fi

    # Set up the 'openstack_citest' user and database in each backend
    tmp_dir=$(mktemp -d)
    trap "rm -rf $tmp_dir" EXIT

    cat << EOF > $tmp_dir/mysql.sql
CREATE DATABASE openstack_citest;
CREATE USER 'openstack_citest'@'localhost' IDENTIFIED BY 'openstack_citest';
CREATE USER 'openstack_citest' IDENTIFIED BY 'openstack_citest';
GRANT ALL PRIVILEGES ON *.* TO 'openstack_citest'@'localhost';
GRANT ALL PRIVILEGES ON *.* TO 'openstack_citest';
FLUSH PRIVILEGES;
EOF
    /usr/bin/mysql -u root < $tmp_dir/mysql.sql

    if [[ "$install_pg" == "True" ]]; then
        cat << EOF > $tmp_dir/postgresql.sql
CREATE USER openstack_citest WITH CREATEDB LOGIN PASSWORD 'openstack_citest';
CREATE DATABASE openstack_citest WITH OWNER openstack_citest;
EOF

        # User/group postgres needs to be given access to tmp_dir
        setfacl -m g:postgres:rwx $tmp_dir
        sudo -u postgres /usr/bin/psql --file=$tmp_dir/postgresql.sql
    fi
}


function _install_infra {
    echo_summary "Installing infra"

    pip_install -U virtualenv
    source $DEVSTACK_PATH/lib/infra
    install_infra
}


function _install_opendaylight {
    echo_summary "Install OpenDaylight"

    # fake up necessary environment for odl to install/configure
    source $DEVSTACK_PATH/lib/neutron-legacy
    neutron_plugin_configure_common
    _create_neutron_conf_dir
    mkdir -p $NEUTRON_CONF_DIR
    touch $NEUTRON_CONF
    mkdir -p /$Q_PLUGIN_CONF_PATH
    Q_PLUGIN_CONF_FILE=$Q_PLUGIN_CONF_PATH/$Q_PLUGIN_CONF_FILENAME
    touch /$Q_PLUGIN_CONF_FILE

    NETWORKING_ODL_DIR=${NETWORKING_ODL_DIR:-$REPO_BASE/networking-odl}
    ODL_V2DRIVER=${ODL_V2DRIVER:-True}
    Q_USE_PUBLIC_VETH=False
    ODL_DONT_WAIT_OVS_BR=True
    # openstack service provider isn't needed, only ODL neutron northbound
    # is necessary for functional test
    ODL_NETVIRT_KARAF_FEATURE=odl-neutron-service,odl-restconf-all,odl-aaa-authn,odl-dlux-core,odl-mdsal-apidocs,odl-neutron-logger
    ODL_BOOT_WAIT_URL=controller/nb/v2/neutron/networks
    source $NETWORKING_ODL_DIR/devstack/settings.odl

    local ODL_NEUTRON_NETWORK_WAIT_URL=controller/nb/v2/neutron/networks
    set +e
    curl -o /dev/null --fail --silent --head -u \
         ${ODL_USERNAME}:${ODL_PASSWORD} \
         http://${ODL_MGR_HOST}:${ODL_PORT}/${ODL_NEUTRON_NETWORK_WAIT_URL}
    local result=$?
    set -e
    if [ $result -eq 0 ]; then
        echo_summary "OpenDaylight config appears to be complete, skipping"
        return 0
    fi

    enable_service odl-server
    source $NETWORKING_ODL_DIR/devstack/plugin.sh stack install
    source $NETWORKING_ODL_DIR/devstack/plugin.sh stack post-config

    $ODL_DIR/*karaf-*/bin/client "feature:list -i"
}


function _install_post_devstack {
    echo_summary "Performing post-devstack installation"
    _install_databases

    # networkign-odl devstack plugin requires infra
    _install_infra
    _install_opendaylight

    if is_ubuntu; then
        install_package isc-dhcp-client
        install_package netcat-openbsd
    elif is_fedora; then
        install_package dhclient
    else
        exit_distro_not_supported "installing dhclient package"
    fi
}


function configure_host_for_func_testing {
    echo_summary "Configuring host for functional testing"

    if [[ "$INSTALL_BASE_DEPENDENCIES" == "True" ]]; then
        # Installing of the following can be achieved via devstack by
        # installing Networking ODL, so their installation is conditional to
        # minimize the work to do on a devstack-configured host.
        _install_base_deps
    fi
    _install_post_devstack
}

# This function has been added because it's called by the devstack scripts
# but since functional is not stacking devstack entirely this
# this function is never imported. Thus, the creation of this no-op function
function conductor_conf {
    :
}

_init


if [[ "$IS_GATE" != "True" ]]; then
    if [[ "$INSTALL_MYSQL_ONLY" == "True" ]]; then
        _install_databases nopg
    else
        configure_host_for_func_testing
    fi
fi
