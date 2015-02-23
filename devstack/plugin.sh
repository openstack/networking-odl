#!/bin/bash
#
# devstack/plugin.sh
# Functions to control the configuration and operation of the opendaylight service

# Dependencies:
#
# ``functions`` file
# ``DEST`` must be defined
# ``STACK_USER`` must be defined

# ``stack.sh`` calls the entry points in this order:
#
# - is_opendaylight_enabled
# - is_opendaylight-compute_enabled
# - install_opendaylight
# - install_opendaylight-compute
# - configure_opendaylight
# - init_opendaylight
# - start_opendaylight
# - stop_opendaylight-compute
# - stop_opendaylight
# - cleanup_opendaylight

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set +o xtrace


# For OVS_BRIDGE and PUBLIC_BRIDGE
source $TOP_DIR/lib/neutron_plugins/ovs_base

# Defaults
# --------

# The IP address of ODL. Set this in local.conf.
# ODL_MGR_IP=
ODL_MGR_IP=${ODL_MGR_IP:-$SERVICE_HOST}

# The default ODL port for Tomcat to use
ODL_PORT=${ODL_PORT:-8088}

# The ODL endpoint URL
ODL_ENDPOINT=${ODL_ENDPOINT:-http://${ODL_MGR_IP}:${ODL_PORT}/controller/nb/v2/neutron}

# The ODL username
ODL_USERNAME=${ODL_USERNAME:-admin}

# The ODL password
ODL_PASSWORD=${ODL_PASSWORD:-admin}

# Short name of ODL package
ODL_NAME=${ODL_NAME:-distribution-karaf-0.2.2-Helium-SR2}

# <define global variables here that belong to this project>
ODL_DIR=$DEST/opendaylight

# The OpenDaylight Package, currently using 'Helium' release
ODL_PKG=${ODL_PKG:-distribution-karaf-0.2.2-Helium-SR2.zip}

# The OpenDaylight URL
ODL_URL=${ODL_URL:-https://nexus.opendaylight.org/content/repositories/public/org/opendaylight/integration/distribution-karaf/0.2.2-Helium-SR2/}

# The OpenDaylight Networking-ODL DIR
ODL_NETWORKING_DIR=$DEST/networking-odl

# Default arguments for OpenDaylight. This is typically used to set
# Java memory options.
# ``ODL_ARGS=Xmx1024m -XX:MaxPermSize=512m``
ODL_ARGS=${ODL_ARGS:-"-XX:MaxPermSize=384m"}

# How long to pause after ODL starts to let it complete booting
ODL_BOOT_WAIT=${ODL_BOOT_WAIT:-300}

# The physical provider network to device mapping
ODL_PROVIDER_MAPPINGS=${ODL_PROVIDER_MAPPINGS:-physnet1:eth1}

# Enable OpenDaylight l3 forwarding
ODL_L3=${ODL_L3:-False}

# Enable debug logs for odl ovsdb
ODL_NETVIRT_DEBUG_LOGS=${ODL_NETVIRT_DEBUG_LOGS:-False}

# The logging config file in ODL
ODL_LOGGING_CONFIG=${ODL_LOGGING_CONFIG:-${ODL_DIR}/${ODL_NAME}/etc/org.ops4j.pax.logging.cfg}

# Entry Points
# ------------

# Test if OpenDaylight is enabled
# is_opendaylight_enabled
function is_opendaylight_enabled {
    [[ ,${ENABLED_SERVICES} =~ ,"odl-" ]] && return 0
    return 1
}

# cleanup_opendaylight() - Remove residual data files, anything left over from previous
# runs that a clean run would need to clean up
function cleanup_opendaylight {
    :
}

# configure_opendaylight() - Set config files, create data dirs, etc
function configure_opendaylight {
    echo "Configuring OpenDaylight"
    # Add odl-ovsdb-openstack if it's not already there
    local ODLOVSDB=$(cat $ODL_DIR/$ODL_NAME/etc/org.apache.karaf.features.cfg | grep featuresBoot= | grep odl)
    if [ "$ODLOVSDB" == "" ]; then
        sed -i '/^featuresBoot=/ s/$/,odl-ovsdb-openstack/' $ODL_DIR/$ODL_NAME/etc/org.apache.karaf.features.cfg
    fi

    # Move Tomcat to 8088
    local _ODLPORT=$(cat $ODL_DIR/$ODL_NAME/configuration/tomcat-server.xml | grep $ODL_PORT)
    if [ "$_ODLPORT" == "" ]; then
        sed -i '/\<Connector port/ s/8080/8088/' $ODL_DIR/$ODL_NAME/configuration/tomcat-server.xml
    fi
    _CONTENTS=$(cat $ODL_DIR/$ODL_NAME/configuration/tomcat-server.xml)
    echo "Contents of tomcat-server.xml file:"
    echo "$_CONTENTS"

    # Configure OpenFlow 1.3 if it's not there
    local OFLOW13=$(cat $ODL_DIR/$ODL_NAME/etc/custom.properties | grep ^of.version)
    if [ "$OFLOW13" == "" ]; then
        echo "ovsdb.of.version=1.3" >> $ODL_DIR/$ODL_NAME/etc/custom.properties
    fi

    # Configure L3 if the user wants it
    if [ "${ODL_L3}" == "True" ]; then
        # Configure L3 FWD if it's not there
        local L3FWD=$(cat $ODL_DIR/$ODL_NAME/etc/custom.properties | grep ^ovsdb.l3.fwd.enabled)
        if [ "$L3FWD" == "" ]; then
            echo "ovsdb.l3.fwd.enabled=yes" >> $ODL_DIR/$ODL_NAME/etc/custom.properties
        fi
    fi

    # Configure DEBUG logs for network virtualization in odl, if the user wants it
    if [ "${ODL_NETVIRT_DEBUG_LOGS}" == "True" ]; then
        local OVSDB_DEBUG_LOGS=$(cat $ODL_LOGGING_CONFIG | grep ^log4j.logger.org.opendaylight.ovsdb)
        if [ "${OVSDB_DEBUG_LOGS}" == "" ]; then
            echo 'log4j.logger.org.opendaylight.ovsdb = TRACE' >> $ODL_LOGGING_CONFIG
            echo 'log4j.logger.org.opendaylight.ovsdb.lib = INFO' >> $ODL_LOGGING_CONFIG
            echo 'log4j.logger.org.opendaylight.ovsdb.openstack.netvirt.impl.NeutronL3Adapter = DEBUG' >> $ODL_LOGGING_CONFIG
            echo 'log4j.logger.org.opendaylight.ovsdb.openstack.netvirt.impl.TenantNetworkManagerImpl = DEBUG' >> $ODL_LOGGING_CONFIG
            echo 'log4j.logger.org.opendaylight.ovsdb.plugin.md.OvsdbInventoryManager = INFO' >> $ODL_LOGGING_CONFIG
        fi
        local ODL_NEUTRON_DEBUG_LOGS=$(cat $ODL_LOGGING_CONFIG | grep ^log4j.logger.org.opendaylight.controller.networkconfig.neutron)
        if [ "${ODL_NEUTRON_DEBUG_LOGS}" == "" ]; then
            echo 'log4j.logger.org.opendaylight.controller.networkconfig.neutron = TRACE' >> $ODL_LOGGING_CONFIG
        fi
    fi
}

function configure_ml2_odl {
    echo "Configuring ML2 for OpenDaylight"
    populate_ml2_config /$Q_PLUGIN_CONF_FILE ml2_odl url=$ODL_ENDPOINT
    populate_ml2_config /$Q_PLUGIN_CONF_FILE ml2_odl username=$ODL_USERNAME
    populate_ml2_config /$Q_PLUGIN_CONF_FILE ml2_odl password=$ODL_PASSWORD
}

# init_opendaylight() - Initialize databases, etc.
function init_opendaylight {
    # clean up from previous (possibly aborted) runs
    # create required data files
    :
}

# install_opendaylight() - Collect source and prepare
function install_opendaylight {
    local _pwd=$(pwd)
    echo "Installing OpenDaylight and dependent packages"

    if is_ubuntu; then
        install_package maven openjdk-7-jre openjdk-7-jdk
    else
        yum_install maven java-1.7.0-openjdk
    fi

    install_opendaylight_neutron_thin_ml2_driver

    # Download OpenDaylight
    mkdir -p $ODL_DIR
    cd $ODL_DIR
    wget -N $ODL_URL/$ODL_PKG
    unzip -u $ODL_PKG
}

function install_opendaylight_neutron_thin_ml2_driver {
    cd $ODL_NETWORKING_DIR
    echo "Installing the Networking-ODL driver for OpenDaylight"
    sudo python setup.py install
}

# install_opendaylight-compute - Make sure OVS is installed
function install_opendaylight-compute {
    # packages are the same as for Neutron OVS agent
    _neutron_ovs_base_install_agent_packages
}

# start_opendaylight() - Start running processes, including screen
function start_opendaylight {
    echo "Starting OpenDaylight"
    if is_ubuntu; then
        JHOME=/usr/lib/jvm/java-1.7.0-openjdk-amd64
    else
        JHOME=/usr/lib/jvm/java-1.7.0-openjdk
    fi
    echo "JHOME set to: $JHOME"

    # The flags to ODL have the following meaning:
    #   -of13: runs ODL using OpenFlow 1.3 protocol support.
    #   -virt ovsdb: Runs ODL in "virtualization" mode with OVSDB support

    echo "About to run: JAVE_HOME=$JHOME $ODL_DIR/$ODL_NAME/bin/karaf"
    export JAVA_HOME=$JHOME
    run_process odl-server "$ODL_DIR/$ODL_NAME/bin/karaf"

    echo "Sleeping now while we wait for OpenDaylight to fire up"
    # Sleep a bit to let OpenDaylight finish starting up
    sleep $ODL_BOOT_WAIT
}

# stop_opendaylight() - Stop running processes (non-screen)
function stop_opendaylight {
    stop_process odl-server
}

# stop_opendaylight-compute() - Remove OVS bridges
function stop_opendaylight-compute {
    # remove all OVS ports that look like Neutron created ports
    for port in $(sudo ovs-vsctl list port | grep -o -e tap[0-9a-f\-]* -e q[rg]-[0-9a-f\-]*); do
        sudo ovs-vsctl del-port ${port}
    done

    # remove all OVS bridges created by Neutron
    for bridge in $(sudo ovs-vsctl list-br | grep -o -e ${OVS_BRIDGE} -e ${PUBLIC_BRIDGE}); do
        sudo ovs-vsctl del-br ${bridge}
    done
}

# main loop
if is_service_enabled odl-server; then
    if [[ "$1" == "source" ]]; then
        # no-op
        :
    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        if [[ "$OFFLINE" != "True" ]]; then
            install_opendaylight
        fi
        configure_opendaylight
        init_opendaylight
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        configure_ml2_odl
        # This has to start before Neutron
        start_opendaylight
    elif [[ "$1" == "stack" && "$2" == "post-extra" ]]; then
        # no-op
        :
    fi

    if [[ "$1" == "unstack" ]]; then
        stop_opendaylight
        cleanup_opendaylight
    fi

    if [[ "$1" == "clean" ]]; then
        # no-op
        :
    fi
fi

if is_service_enabled odl-neutron; then
    if [[ "$1" == "source" ]]; then
        # no-op
        :
    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        install_opendaylight_neutron_thin_ml2_driver
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        configure_ml2_odl
    elif [[ "$1" == "stack" && "$2" == "post-extra" ]]; then
        # no-op
        :
    fi

    if [[ "$1" == "unstack" ]]; then
        # no-op
        :
    fi

    if [[ "$1" == "clean" ]]; then
        # no-op
        :
    fi
fi

if is_service_enabled odl-compute; then
    if [[ "$1" == "source" ]]; then
        # no-op
        :
    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        install_opendaylight-compute
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        if is_service_enabled nova; then
            create_nova_conf_neutron
        fi
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Initializing OpenDaylight"
        ODL_LOCAL_IP=${ODL_LOCAL_IP:-$HOST_IP}
        ODL_MGR_PORT=${ODL_MGR_PORT:-6640}
        read ovstbl <<< $(sudo ovs-vsctl get Open_vSwitch . _uuid)
        sudo ovs-vsctl set-manager tcp:$ODL_MGR_IP:$ODL_MGR_PORT
        if [[ -n "$ODL_PROVIDER_MAPPINGS" ]] && [[ "$ENABLE_TENANT_VLANS" == "True" ]]; then
            sudo ovs-vsctl set Open_vSwitch $ovstbl \
                other_config:provider_mappings=$ODL_PROVIDER_MAPPINGS
        fi
        sudo ovs-vsctl set Open_vSwitch $ovstbl other_config:local_ip=$ODL_LOCAL_IP
    elif [[ "$1" == "stack" && "$2" == "post-extra" ]]; then
        # no-op
        :
    fi

    if [[ "$1" == "unstack" ]]; then
        sudo ovs-vsctl del-manager
        BRIDGES=$(sudo ovs-vsctl list-br)
        for bridge in $BRIDGES ; do
            sudo ovs-vsctl del-controller $bridge
        done

        stop_opendaylight-compute
    fi

    if [[ "$1" == "clean" ]]; then
        # no-op
        :
    fi
fi
# Restore xtrace
$XTRACE

# Tell emacs to use shell-script-mode
## Local variables:
## mode: shell-script
## End:
