#!/bin/bash
#
# devstack/plugin.sh
# Functions to control the configuration and operation of the opendaylight service

# Dependencies:
#
# ``functions`` file
# ``DEST`` must be defined
# ``STACK_USER`` must be defined
# ``DATA_DIR`` must be defined

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

# OpenDaylight directories
NETWORKING_ODL_DIR=$DEST/networking-odl
ODL_DIR=$DEST/opendaylight

# Make sure $ODL_DIR exists
mkdir -p $ODL_DIR

# Import common functions
source $TOP_DIR/functions

# For OVS_BRIDGE and PUBLIC_BRIDGE
source $TOP_DIR/lib/neutron_plugins/ovs_base

# Source global ODL settings
source $NETWORKING_ODL_DIR/devstack/settings.odl

# Source specicic ODL release settings
function odl_update_maven_metadata_xml {
    local MAVENMETAFILE=$1
    local NEXUSPATH=$2
    local BUNDLEVERSION=$3

    if [[ "$OFFLINE" == "True" ]]; then
        return
    fi

    # Remove stale MAVENMETAFILE for cases where you switch releases
    rm -f $MAVENMETAFILE

    # Acquire the timestamp information from maven-metadata.xml
    wget -O $MAVENMETAFILE ${NEXUSPATH}/${BUNDLEVERSION}/maven-metadata.xml
}

source $NETWORKING_ODL_DIR/devstack/odl-releases/$ODL_RELEASE

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

    sudo ovs-vsctl --no-wait -- --may-exist add-br $OVS_BR
    sudo ovs-vsctl --no-wait br-set-external-id $OVS_BR bridge-id $OVS_BR

    # The logging config file in ODL
    local ODL_LOGGING_CONFIG=${ODL_DIR}/${ODL_NAME}/etc/org.ops4j.pax.logging.cfg

    # Add netvirt feature in Karaf, if it's not already there
    local ODLFEATUREMATCH=$(cat $ODL_DIR/$ODL_NAME/etc/org.apache.karaf.features.cfg | grep featuresBoot= | grep $ODL_NETVIRT_KARAF_FEATURE)
    if [ "$ODLFEATUREMATCH" == "" ]; then
        sed -i "/^featuresBoot=/ s/$/,$ODL_NETVIRT_KARAF_FEATURE/" $ODL_DIR/$ODL_NAME/etc/org.apache.karaf.features.cfg
    fi

    if [[ "$ODL_RELEASE" =~ "helium" ]]; then
        # Move Tomcat to $ODL_PORT
        local _ODLPORT=$(cat $ODL_DIR/$ODL_NAME/configuration/tomcat-server.xml | grep $ODL_PORT)
        if [ "$_ODLPORT" == "" ]; then
            sed -i "/\<Connector port/ s/808./$ODL_PORT/" $ODL_DIR/$ODL_NAME/configuration/tomcat-server.xml
        fi
    else
        # Move Jetty to $ODL_PORT
        local _ODLPORT=$(cat $ODL_DIR/$ODL_NAME/etc/jetty.xml | grep $ODL_PORT)
        if [ "$_ODLPORT" == "" ]; then
            sed -i "/\<Property name\=\"jetty\.port/ s/808./$ODL_PORT/" $ODL_DIR/$ODL_NAME/etc/jetty.xml
        fi
    fi

    # Configure L3 if the user wants it
    if [ "${ODL_L3}" == "True" ]; then
        # Configure L3 FWD if it's not there
        local L3FWD=$(cat $ODL_DIR/$ODL_NAME/etc/custom.properties | grep ^ovsdb.l3.fwd.enabled)
        if [ "$L3FWD" == "" ]; then
            echo "ovsdb.l3.fwd.enabled=yes" >> $ODL_DIR/$ODL_NAME/etc/custom.properties
        fi
    fi

    # Remove existing logfiles
    rm -f "/opt/stack/logs/$ODL_KARAF_LOG_BASE*"
    # Log karaf output to a file
    _LF=/opt/stack/logs/$ODL_KARAF_LOG_NAME
    LF=$(echo $_LF | sed 's/\//\\\//g')
    # Soft link for easy consumption
    ln -sf $_LF "/opt/stack/logs/screen-karaf.txt"

    # Change the karaf logfile
    sed -i "/^log4j\.appender\.out\.file/ s/.*/log4j\.appender\.out\.file\=$LF/" \
    $ODL_DIR/$ODL_NAME/etc/org.ops4j.pax.logging.cfg

    # Configure DEBUG logs for network virtualization in odl, if the user wants it
    if [ "${ODL_NETVIRT_DEBUG_LOGS}" == "True" ]; then
        local OVSDB_DEBUG_LOGS=$(cat $ODL_LOGGING_CONFIG | grep ^log4j.logger.org.opendaylight.ovsdb)
        if [ "${OVSDB_DEBUG_LOGS}" == "" ]; then
            echo 'log4j.logger.org.opendaylight.ovsdb = TRACE, out' >> $ODL_LOGGING_CONFIG
            echo 'log4j.logger.org.opendaylight.ovsdb.lib = INFO, out' >> $ODL_LOGGING_CONFIG
            echo 'log4j.logger.org.opendaylight.ovsdb.openstack.netvirt.impl.NeutronL3Adapter = DEBUG, out' >> $ODL_LOGGING_CONFIG
            echo 'log4j.logger.org.opendaylight.ovsdb.openstack.netvirt.impl.TenantNetworkManagerImpl = DEBUG, out' >> $ODL_LOGGING_CONFIG
            echo 'log4j.logger.org.opendaylight.ovsdb.plugin.md.OvsdbInventoryManager = INFO, out' >> $ODL_LOGGING_CONFIG
        fi
        if [[ "$ODL_RELEASE" =~ "helium" ]]; then
            local ODL_NEUTRON_DEBUG_LOGS=$(cat $ODL_LOGGING_CONFIG | grep ^log4j.logger.org.opendaylight.controller.networkconfig.neutron)
            if [ "${ODL_NEUTRON_DEBUG_LOGS}" == "" ]; then
                echo 'log4j.logger.org.opendaylight.controller.networkconfig.neutron = TRACE, out' >> $ODL_LOGGING_CONFIG
            fi
        else
            local ODL_NEUTRON_DEBUG_LOGS=$(cat $ODL_LOGGING_CONFIG | grep ^log4j.logger.org.opendaylight.neutron)
            if [ "${ODL_NEUTRON_DEBUG_LOGS}" == "" ]; then
                echo 'log4j.logger.org.opendaylight.neutron = TRACE, out' >> $ODL_LOGGING_CONFIG
            fi
        fi
        # Bump up how man logfiles we save after rotation if debug is turned on
        sed -i "/^log4j.appender.out.maxBackupIndex=/ s/10/$ODL_LOGFILES_TO_SAVE/" $ODL_LOGGING_CONFIG
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
    echo "Installing OpenDaylight and dependent packages"

    if is_ubuntu; then
        install_package maven openjdk-7-jre openjdk-7-jdk
    else
        yum_install maven java-1.7.0-openjdk
    fi

    install_opendaylight_neutron_thin_ml2_driver

    # Download OpenDaylight
    cd $ODL_DIR

    if [[ "$OFFLINE" != "True" ]]; then
	wget -N $ODL_URL/$ODL_PKG
    fi
    unzip -u -o $ODL_PKG
}

function install_opendaylight_neutron_thin_ml2_driver {
    cd $NETWORKING_ODL_DIR
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

    # Wipe out the data directory ... grumble grumble grumble
    rm -rf $ODL_DIR/$ODL_NAME/data

    # The following variables are needed by the running karaf process.
    # See the "bin/setenv" file in the OpenDaylight distribution for
    # their individual meaning.
    export JAVA_HOME=$JHOME
    export JAVA_MIN_MEM=$ODL_JAVA_MIN_MEM
    export JAVA_MAX_MEM=$ODL_JAVA_MAX_MEM
    export JAVA_MAX_PERM_MEM=$ODL_JAVA_MAX_PERM_MEM
    run_process odl-server "$ODL_DIR/$ODL_NAME/bin/start"

    # Sleep a bit to let OpenDaylight finish starting up
    sleep $ODL_BOOT_WAIT
}

# stop_opendaylight() - Stop running processes (non-screen)
function stop_opendaylight {
    # Stop the karaf container
    $ODL_DIR/$ODL_NAME/bin/stop
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
        setup_opendaylight_package
        install_opendaylight
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

        # Configure public bridge to be used by ODL_L3
        if [ "${ODL_L3}" == "True" ]; then
            sudo ovs-vsctl --no-wait -- --may-exist add-br $PUBLIC_BRIDGE
            sudo ovs-vsctl --no-wait br-set-external-id $PUBLIC_BRIDGE bridge-id $PUBLIC_BRIDGE

            # Add public interface to public bridge, if provided
            if [ -n "$PUBLIC_INTERFACE" ]; then
                sudo ovs-vsctl add-port $PUBLIC_BRIDGE $PUBLIC_INTERFACE
                sudo ip link set $PUBLIC_INTERFACE up
            fi
        fi
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
