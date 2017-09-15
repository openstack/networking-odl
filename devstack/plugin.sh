#!/bin/bash
#
# devstack/plugin.sh
# Functions to control the configuration and operation of the opendaylight service

# Save trace setting
_XTRACE_NETWORKING_ODL=$(set +o | grep xtrace)
set +o xtrace

# OpenDaylight directories
NETWORKING_ODL_DIR=${NETWORKING_ODL_DIR:-$DEST/networking-odl}
ODL_DIR=$DEST/opendaylight

# Make sure $ODL_DIR exists
mkdir -p $ODL_DIR

# Import utility functions
source $TOP_DIR/functions
source $NETWORKING_ODL_DIR/devstack/functions
source $TOP_DIR/lib/neutron

# Import bridge data
source $TOP_DIR/lib/neutron_plugins/ovs_base

# Import ODL settings
source $NETWORKING_ODL_DIR/devstack/settings.odl
if [ -r $NETWORKING_ODL_DIR/devstack/odl-releases/$ODL_RELEASE ]; then
    source $NETWORKING_ODL_DIR/devstack/odl-releases/$ODL_RELEASE
fi
source $NETWORKING_ODL_DIR/devstack/odl-releases/common $ODL_RELEASE

# Utilities functions for setting up Java
source $NETWORKING_ODL_DIR/devstack/setup_java.sh

# Import Entry Points
# -------------------
source $NETWORKING_ODL_DIR/devstack/entry_points

# Restore xtrace
$_XTRACE_NETWORKING_ODL

if [[ "$ODL_USING_EXISTING_JAVA" == "True" ]]; then
    echo 'Using installed java.'
    java -version || exit 1
fi

# main loop
if is_service_enabled odl-server; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        install_networking_odl
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

    if [[ "$1" == "unstack" && "$UNSTACK_KEEP_ODL" != "True" ]]; then
        stop_opendaylight
        cleanup_opendaylight
    fi

    if [[ "$1" == "clean" ]]; then
        stop_opendaylight
        cleanup_opendaylight
    fi
fi

if is_service_enabled odl-compute; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        install_networking_odl
        install_opendaylight_compute
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        if is_service_enabled nova; then
            configure_neutron_nova
        fi
        bind_opendaylight_controller
        if [[ -z "$ODL_DONT_WAIT_OVS_BR" ]]; then
            wait_for_active_bridge $OVS_BR $ODL_RETRY_SLEEP_INTERVAL $ODL_BOOT_WAIT
        fi

        # L3 needs to be configured only for netvirt-ovsdb - in netvirt-vpnservice L3 is configured
        # by provider_mappings, and the provider mappings are added to br-int by default
        if [[ "${ODL_L3}" == "True" ]]; then
            configure_opendaylight_l3
        fi
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # no-op
        :
    elif [[ "$1" == "stack" && "$2" == "post-extra" ]]; then
        # no-op
        :
    fi

    if [[ "$1" == "unstack" && "$UNSTACK_KEEP_ODL" != "True" ]]; then
        cleanup_opendaylight_compute
    fi

    if [[ "$1" == "clean" ]]; then
        # no-op
        :
    fi
fi

if is_service_enabled odl-neutron; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        install_networking_odl
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
        install_networking_odl
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
