#!/usr/bin/env bash

set -xe

# Drop a token that marks the build as coming from openstack infra
GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack
# for localrc_set
source $DEVSTACK_PATH/inc/ini-config

case "$ODL_RELEASE_BASE" in
    latest-snapshot)
        ODL_RELEASE=latest-snapshot
        ;;
    carbon-snapshot)
        ODL_RELEASE=carbon-snapshot-0.6
        ;;
    boron-snapshot)
        ODL_RELEASE=boron-snapshot-0.5
        ;;
    beryllium-snapshot)
        ODL_RELEASE=beryllium-snapshot-0.4.5
        ;;
    *)
        echo "Unknown ODL release base: $ODL_RELEASE_BASE"
        exit 1
        ;;
esac

case "$ODL_GATE_V2DRIVER" in
    v2driver)
        ODL_V2DRIVER=True
        ;;
    v1driver|*)
        ODL_V2DRIVER=False
        ;;
esac

case "$ODL_GATE_PORT_BINDING" in
    pseudo-agentdb-binding)
        ODL_PORT_BINDING_CONTROLLER=pseudo-agentdb-binding
        ;;
    legacy-port-binding)
        ODL_PORT_BINDING_CONTROLLER=legacy-port-binding
        ;;
    network-topology|*)
        ODL_PORT_BINDING_CONTROLLER=network-topology
        ;;
esac

case "$ODL_GATE_SERVICE_PROVIDER" in
    vpnservice)
        ODL_NETVIRT_KARAF_FEATURE=odl-neutron-service,odl-restconf-all,odl-aaa-authn,odl-dlux-core,odl-mdsal-apidocs,odl-netvirt-openstack
        ;;
    netvirt|*)
        ODL_NETVIRT_KARAF_FEATURE=odl-neutron-service,odl-restconf-all,odl-aaa-authn,odl-dlux-core,odl-mdsal-apidocs,odl-ovsdb-openstack
        ;;
esac
# add odl-neutron-logger for debugging
# odl-neutorn-logger has been introduced from boron cycle
case "$ODL_RELEASE_BASE" in
    carbon-snapshot|boron-snapshot)
        ODL_NETVIRT_KARAF_FEATURE=$ODL_NETVIRT_KARAF_FEATURE,odl-neutron-logger
        ;;
    *)
        ;;
esac

local localrc_file=$DEVSTACK_PATH/local.conf

localrc_set $localrc_file "IS_GATE" "True"

# Set here the ODL release to use for the Gate job
localrc_set $localrc_file "ODL_RELEASE" "${ODL_RELEASE}"

# Set here which driver, v1 or v2 driver
localrc_set $localrc_file "ODL_V2DRIVER" "${ODL_V2DRIVER}"

# Set here which port binding controller
localrc_set $localrc_file "ODL_PORT_BINDING_CONTROLLER" "${ODL_PORT_BINDING_CONTROLLER}"

# Set here which ODL openstack service provider to use
localrc_set $localrc_file "ODL_NETVIRT_KARAF_FEATURE" "${ODL_NETVIRT_KARAF_FEATURE}"

# Switch to using the ODL's L3 implementation
localrc_set $localrc_file "ODL_L3" "True"

# TODO(yamahata): only for legacy netvirt
# Since localrc_set adds it in reverse order, ODL_PROVIDER_MAPPINGS needs to be
# before depending variables
localrc_set $localrc_file "ODL_PROVIDER_MAPPINGS" "\${ODL_PROVIDER_MAPPINGS:-br-ex:\${Q_PUBLIC_VETH_INT}}"
localrc_set $localrc_file "Q_USE_PUBLIC_VETH" "True"
localrc_set $localrc_file "Q_PUBLIC_VETH_EX" "veth-pub-ex"
localrc_set $localrc_file "Q_PUBLIC_VETH_INT" "veth-pub-int"

# Enable debug logs for odl ovsdb
localrc_set $localrc_file "ODL_NETVIRT_DEBUG_LOGS" "True"
