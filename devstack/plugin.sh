#!/bin/bash
#
# devstack/plugin.sh
# Functions to control the configuration and operation of the opendaylight service

# Save trace setting
_XTRACE_NETWORKING_ODL=$(set +o | grep xtrace)
set +o xtrace

# OpenDaylight directories
NETWORKING_ODL_DIR=$DEST/networking-odl
ODL_DIR=$DEST/opendaylight

# Make sure $ODL_DIR exists
mkdir -p $ODL_DIR

# Import utility functions
source $TOP_DIR/functions
source $NETWORKING_ODL_DIR/devstack/functions

# Import bridge data
source $TOP_DIR/lib/neutron_plugins/ovs_base

# Import ODL settings
source $NETWORKING_ODL_DIR/devstack/settings.odl
source $NETWORKING_ODL_DIR/devstack/odl-releases/$ODL_RELEASE

# Utilities functions for setting up Java
source $NETWORKING_ODL_DIR/devstack/setup_java.sh

# Import Entry Points
# -------------------
source $NETWORKING_ODL_DIR/devstack/entry_points

# Restore xtrace
$_XTRACE_NETWORKING_ODL

if [[ "$ODL_USING_EXISTING_JAVA" == "True" ]]
then
    echo 'Using installed java.'
    java -version || exit 1
fi

# main loop
if is_service_enabled odl-server; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        setup_opendaylight_package
        install_opendaylight
        configure_opendaylight
        init_opendaylight
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        configure_neutron_odl
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

if is_service_enabled odl-compute; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        install_opendaylight_compute
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        if is_service_enabled nova; then
            create_nova_conf_neutron
        fi
        bind_opendaylight_controller
        wait_for_active_bridge $OVS_BR $ODL_RETRY_SLEEP_INTERVAL $ODL_BOOT_WAIT
        if [ "${ODL_L3}" == "True" ]; then
            configure_opendaylight_l3
        fi
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # no-op
        :
    elif [[ "$1" == "stack" && "$2" == "post-extra" ]]; then
        # no-op
        :
    fi

    if [[ "$1" == "unstack" ]]; then
        cleanup_opendaylight_compute
    fi

    if [[ "$1" == "clean" ]]; then
        # no-op
        :
    fi
fi

if is_service_enabled odl-neutron; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        install_opendaylight_neutron_thin_ml2_driver
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        configure_neutron_odl
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

if is_service_enabled odl-lightweight-testing; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        install_opendaylight_neutron_thin_ml2_driver
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        configure_neutron_odl
        configure_neutron_odl_lightweight_testing
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

# Tell emacs to use shell-script-mode
## Local variables:
## mode: shell-script
## End:
