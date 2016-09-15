#!/usr/bin/env bash

set -xe

# Drop a token that marks the build as coming from openstack infra
GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

case "$ODL_RELEASE_BASE" in
    carbon-snapshot)
        ODL_RELEASE=carbon-snapshot-0.6.0
        ;;
    boron-snapshot)
        ODL_RELEASE=boron-snapshot-0.5.1
        ;;
    beryllium-snapshot)
        ODL_RELEASE=beryllium-snapshot-0.4.4
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

cat <<EOF >> $DEVSTACK_PATH/localrc

IS_GATE=True

# Set here the ODL release to use for the Gate job
ODL_RELEASE=${ODL_RELEASE}

# Set here which driver, v1 or v2 driver
ODL_V2DRIVER=${ODL_V2DRIVER}

# Set here which port binding controller
ODL_PORT_BINDING_CONTROLLER=${ODL_PORT_BINDING_CONTROLLER}

# Set here which ODL openstack service provider to use
ODL_NETVIRT_KARAF_FEATURE=${ODL_NETVIRT_KARAF_FEATURE}

# Switch to using the ODL's L3 implementation
ODL_L3=True

# Enable debug logs for odl ovsdb
ODL_NETVIRT_DEBUG_LOGS=True

EOF
