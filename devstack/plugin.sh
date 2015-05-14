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


# For OVS_BRIDGE and PUBLIC_BRIDGE
source $TOP_DIR/lib/neutron_plugins/ovs_base

# Defaults
# --------

# The IP address of ODL. Set this in local.conf.
# ODL_MGR_IP=
ODL_MGR_IP=${ODL_MGR_IP:-$SERVICE_HOST}

# The default ODL port for Tomcat to use
# NOTE: We make this configurable because by default, ODL uses port 8080 for
# Tomcat (Helium releases) or Jetty (Lithium and later releases), and this
# conflicts with swift which also uses port 8080.
ODL_PORT=${ODL_PORT:-8087}

# The ODL endpoint URL
ODL_ENDPOINT=${ODL_ENDPOINT:-http://${ODL_MGR_IP}:${ODL_PORT}/controller/nb/v2/neutron}

# The ODL username
ODL_USERNAME=${ODL_USERNAME:-admin}

# The ODL password
ODL_PASSWORD=${ODL_PASSWORD:-admin}

# <define global variables here that belong to this project>
ODL_DIR=$DEST/opendaylight

# The OpenDaylight URL PREFIX
ODL_URL_PREFIX=${ODL_URL_PREFIX:-https://nexus.opendaylight.org}

# The OpenDaylight Networking-ODL DIR
ODL_NETWORKING_DIR=$DEST/networking-odl

# How long (in seconds) to pause after ODL starts to let it complete booting
ODL_BOOT_WAIT=${ODL_BOOT_WAIT:-90}

# The physical provider network to device mapping
ODL_PROVIDER_MAPPINGS=${ODL_PROVIDER_MAPPINGS:-physnet1:eth1}

# Enable OpenDaylight l3 forwarding
ODL_L3=${ODL_L3:-False}

# Enable debug logs for odl ovsdb
ODL_NETVIRT_DEBUG_LOGS=${ODL_NETVIRT_DEBUG_LOGS:-False}

# The network virtualization feature used by opendaylight loaded by Karaf
ODL_NETVIRT_KARAF_FEATURE=${ODL_NETVIRT_KARAF_FEATURE:-odl-ovsdb-openstack}

# Karaf logfile information
ODL_KARAF_LOG_NAME=${ODL_KARAF_LOG_NAME:-q-odl-karaf.log}

# The bridge to configure
OVS_BR=${OVS_BR:-br-int}

# Allow the min/max/perm Java memory to be configurable
ODL_JAVA_MIN_MEM=${ODL_JAVA_MIN_MEM:-96m}
ODL_JAVA_MAX_MEM=${ODL_JAVA_MAX_MEM:-256m}
ODL_JAVA_MAX_PERM_MEM=${ODL_JAVA_MAX_PERM_MEM:-256m}

function configure_odl_pkg_vars {
    # This defaults to lithium, so grab the latest lithium nightly build
    if [ "$ODL_RELEASE" == "lithium-snapshot" ]; then

        NEXUSPATH="${ODL_URL_PREFIX}/content/repositories/opendaylight.snapshot/org/opendaylight/integration/distribution-karaf"
        BUNDLEVERSION='0.3.0-SNAPSHOT'
        MAVENMETAFILE=$ODL_DIR/maven-metadata.xml

        if [ ! -f $MAVENMETAFILE ]; then
            # Acquire the timestamp information from maven-metadata.xml
            wget -O $MAVENMETAFILE ${NEXUSPATH}/${BUNDLEVERSION}/maven-metadata.xml
        fi
        if is_ubuntu; then
            BUNDLE_TIMESTAMP=`xpath -e "//snapshotVersion[extension='zip'][1]/value/text()" $MAVENMETAFILE 2>/dev/null`
        else
            BUNDLE_TIMESTAMP=`xpath $MAVENMETAFILE "//snapshotVersion[extension='zip'][1]/value/text()" 2>/dev/null`
        fi
        echo "Nexus timestamp is ${BUNDLE_TIMESTAMP}"

        export ODL_URL=${NEXUSPATH}/${BUNDLEVERSION}
        export ODL_NAME=distribution-karaf-${BUNDLEVERSION}
        export ODL_PKG=distribution-karaf-${BUNDLE_TIMESTAMP}.zip
    else
        # The OpenDaylight URL
        export ODL_URL=${ODL_URL:-${ODL_URL_PREFIX}/content/repositories/public/org/opendaylight/integration/distribution-karaf/0.2.3-Helium-SR3}

        # Short name of ODL package
        export ODL_NAME=${ODL_NAME:-distribution-karaf-0.2.3-Helium-SR3}

        # The OpenDaylight Package, currently using 'Helium' release
        export ODL_PKG=${ODL_PKG:-distribution-karaf-0.2.3-Helium-SR3.zip}
    fi
}

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
    configure_odl_pkg_vars

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

    if [ "$ODL_RELEASE" == "helium" ]; then
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

    # Log karaf output to a file
    _LF=$DEST/logs/$ODL_KARAF_LOG_NAME
    LF=$(echo $_LF | sed 's/\//\\\//g')

    # Remove the existing logfile
    rm -f $_LF*
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
        if [ "$ODL_RELEASE" == "helium" ]; then
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
        install_package maven openjdk-7-jre openjdk-7-jdk libxml-xpath-perl
    else
        yum_install maven java-1.7.0-openjdk perl-XML-XPath
    fi

    install_opendaylight_neutron_thin_ml2_driver

    # Download OpenDaylight
    mkdir -p $ODL_DIR
    cd $ODL_DIR

    configure_odl_pkg_vars
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
    configure_odl_pkg_vars

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

    # Link the logfile
    LF=$DEST/logs/$ODL_KARAF_LOG_NAME
    mkdir -p $DATA_DIR/log
    ln -sf $LF $DATA_DIR/log/screen-karaf.log

    # Sleep a bit to let OpenDaylight finish starting up
    sleep $ODL_BOOT_WAIT
}

# stop_opendaylight() - Stop running processes (non-screen)
function stop_opendaylight {
    configure_odl_pkg_vars

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

        # Configure public bridge to be used by ODL_L3
        if [ "${ODL_L3}" == "True" ]; then
            sudo ovs-vsctl --no-wait -- --may-exist add-br $PUBLIC_BRIDGE
            sudo ovs-vsctl --no-wait br-set-external-id $PUBLIC_BRIDGE bridge-id $PUBLIC_BRIDGE

            # Add public interface to public bridge, if provided
            if [ -n "$PUBLIC_INTERFACE" ]; then
                sudo ovs-vsctl add-port $PUBLIC_BRIDGE $PUBLIC_INTERFACE
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
