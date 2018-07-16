#!/usr/bin/env bash

set -xe

# Drop a token that marks the build as coming from openstack infra
GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack
# for localrc_set
source $DEVSTACK_PATH/inc/ini-config
source $GATE_DEST/networking-odl/devstack/functions

case "$ODL_RELEASE_BASE" in
    latest-snapshot)
        ODL_RELEASE=latest-snapshot
        ;;
    fluorine-snapshot)
        ODL_RELEASE=fluorine-snapshot-0.9
        ;;
    oxygen-snapshot)
        ODL_RELEASE=oxygen-snapshot-0.8
        ;;
    *)
        echo "Unknown ODL release base: $ODL_RELEASE_BASE"
        exit 1
        ;;
esac

ODL_PORT_BINDING_CONTROLLER=pseudo-agentdb-binding

ODL_GATE_SERVICE_PROVIDER=${ODL_GATE_SERVICE_PROVIDER%-}
if [[ -z "$ODL_GATE_SERVICE_PROVIDER" ]]; then
    ODL_GATE_SERVICE_PROVIDER=vpnservice
fi

case "$ODL_GATE_SERVICE_PROVIDER" in
    vpnservice)
        ODL_NETVIRT_KARAF_FEATURE=odl-neutron-service,odl-restconf-all,odl-aaa-authn,odl-dlux-core,odl-mdsal-apidocs,odl-netvirt-openstack
        # $PUBLIC_PHYSICAL_NETWORK = public by default
        ODL_MAPPING_KEY=public
        ;;
    netvirt|*)
        ODL_NETVIRT_KARAF_FEATURE=odl-neutron-service,odl-restconf-all,odl-aaa-authn,odl-dlux-core,odl-mdsal-apidocs,odl-ovsdb-openstack
        # $PUBLIC_BRIDGE = br-ex by default
        ODL_MAPPING_KEY=br-ex
        ;;
esac

ODL_NETVIRT_KARAF_FEATURE=$ODL_NETVIRT_KARAF_FEATURE,odl-neutron-logger

local localrc_file=$DEVSTACK_PATH/local.conf

localrc_set $localrc_file "IS_GATE" "True"

# Set here the ODL release to use for the Gate job
localrc_set $localrc_file "ODL_RELEASE" "${ODL_RELEASE}"

# Set timeout in seconds for http client to ODL neutron northbound
localrc_set $localrc_file "ODL_TIMEOUT" "60"

# Set here which port binding controller
localrc_set $localrc_file "ODL_PORT_BINDING_CONTROLLER" "${ODL_PORT_BINDING_CONTROLLER}"

# Set here which ODL openstack service provider to use
localrc_set $localrc_file "ODL_NETVIRT_KARAF_FEATURE" "${ODL_NETVIRT_KARAF_FEATURE}"

# Switch to using the ODL's L3 implementation
localrc_set $localrc_file "ODL_L3" "True"

# Since localrc_set adds it in reverse order, ODL_PROVIDER_MAPPINGS needs to be
# before depending variables

if [[ "$ODL_GATE_SERVICE_PROVIDER" == "vpnservice" ]]; then
    localrc_set $localrc_file "ODL_PROVIDER_MAPPINGS" "public:br-ex"
    localrc_set $localrc_file "PUBLIC_PHYSICAL_NETWORK" "public"
    localrc_set $localrc_file "PUBLIC_BRIDGE" "br-ex"
    localrc_set $localrc_file "Q_USE_PUBLIC_VETH" "False"
else
    localrc_set $localrc_file "ODL_PROVIDER_MAPPINGS" "\${ODL_PROVIDER_MAPPINGS:-${ODL_MAPPING_KEY}:\${Q_PUBLIC_VETH_INT}}"
    localrc_set $localrc_file "Q_USE_PUBLIC_VETH" "True"
    localrc_set $localrc_file "Q_PUBLIC_VETH_EX" "veth-pub-ex"
    localrc_set $localrc_file "Q_PUBLIC_VETH_INT" "veth-pub-int"
fi

# Enable debug logs for odl ovsdb
localrc_set $localrc_file "ODL_NETVIRT_DEBUG_LOGS" "True"

localrc_set $localrc_file "RALLY_SCENARIO" "${RALLY_SCENARIO}"

# delete and recreate network to workaroud netvirt bug:
# https://bugs.opendaylight.org/show_bug.cgi?id=7456
# https://bugs.opendaylight.org/show_bug.cgi?id=8133
if [[ "$DEVSTACK_GATE_TOPOLOGY" == "multinode" ]]; then
    purge_and_recreate_initial_networks $DEVSTACK_PATH
fi
