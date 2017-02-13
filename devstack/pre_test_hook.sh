#!/usr/bin/env bash

set -xe

# Drop a token that marks the build as coming from openstack infra
GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

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

if [[ -z "$ODL_GATE_V2DRIVER" ]] && [[ -n "${RALLY_SCENARIO}" ]]; then
    ODL_GATE_V2DRIVER=v2driver
fi
case "$ODL_GATE_V2DRIVER" in
    v2driver)
        ODL_V2DRIVER=True
        ;;
    v1driver|*)
        ODL_V2DRIVER=False
        ;;
esac

if [[ -z "$ODL_GATE_PORT_BINDING" ]]; then
    case "$ODL_RELEASE_BASE" in
        beryllium-snapshot)
            # pseudo-agentdb-binding is supported from boron
            ODL_GATE_PORT_BINDING=network-topology
            ;;
        *)
            ODL_GATE_PORT_BINDING=pseudo-agentdb-binding
            ;;
    esac
fi
case "$ODL_GATE_PORT_BINDING" in
    pseudo-agentdb-binding)
        ODL_PORT_BINDING_CONTROLLER=pseudo-agentdb-binding
        ;;
    legacy-port-binding)
        ODL_PORT_BINDING_CONTROLLER=legacy-port-binding
        ;;
    network-topology)
        ODL_PORT_BINDING_CONTROLLER=network-topology
        ;;
    *)
        echo "Unknown port binding controller: $ODL_GATE_PORT_BINDING"
        exit 1
        ;;
esac

ODL_GATE_SERVICE_PROVIDER=${ODL_GATE_SERVICE_PROVIDER%-}
if [[ -z "$ODL_GATE_SERVICE_PROVIDER" ]] && [[ -n "${RALLY_SCENARIO}" ]]; then
    case "$ODL_RELEASE_BASE" in
        beryllium-snapshot)
            # new netvirt was introduced from boron
            ODL_GATE_SERVICE_PROVIDER=netvirt
            ;;
        *)
            ODL_GATE_SERVICE_PROVIDER=vpnservice
            ;;
    esac
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
# add odl-neutron-logger for debugging
# odl-neutorn-logger has been introduced from boron cycle
case "$ODL_RELEASE_BASE" in
    carbon-snapshot|boron-snapshot)
        ODL_NETVIRT_KARAF_FEATURE=$ODL_NETVIRT_KARAF_FEATURE,odl-neutron-logger
        ;;
    *)
        ;;
esac

cat <<EOF >> $DEVSTACK_PATH/localrc

IS_GATE=True

# Set here the ODL release to use for the Gate job
ODL_RELEASE=${ODL_RELEASE}

# Set here which driver, v1 or v2 driver
ODL_V2DRIVER=${ODL_V2DRIVER}

# Set timeout in seconds for http client to ODL neutron northbound
ODL_TIMEOUT=60

# Set here which port binding controller
ODL_PORT_BINDING_CONTROLLER=${ODL_PORT_BINDING_CONTROLLER}

# Set here which ODL openstack service provider to use
ODL_NETVIRT_KARAF_FEATURE=${ODL_NETVIRT_KARAF_FEATURE}

# Switch to using the ODL's L3 implementation
ODL_L3=True

# TODO(yamahata): only for legacy netvirt
Q_USE_PUBLIC_VETH=True
Q_PUBLIC_VETH_EX=veth-pub-ex
Q_PUBLIC_VETH_INT=veth-pub-int
ODL_PROVIDER_MAPPINGS=${ODL_PROVIDER_MAPPINGS:-${ODL_MAPPING_KEY}:\${Q_PUBLIC_VETH_INT}}

# Enable debug logs for odl ovsdb
ODL_NETVIRT_DEBUG_LOGS=True

RALLY_SCENARIO=${RALLY_SCENARIO}

EOF

# delete private network to workaroud netvirt bug:
# https://bugs.opendaylight.org/show_bug.cgi?id=7456
if [[ "$DEVSTACK_GATE_TOPOLOGY" == "multinode" ]] ; then
    cat <<EOF >> $DEVSTACK_PATH/local.sh
#!/usr/bin/env bash

source $DEVSTACK_PATH/openrc admin
rid=\`neutron router-list | grep router1 | cut -f2 -d'|'\`
neutron router-gateway-clear \$rid
neutron router-port-list \$rid | grep subnet_id | cut -f4 -d'"' | xargs -I {} neutron router-interface-delete \$rid {}
neutron router-delete \$rid
neutron subnet-list | grep private | cut -f2 -d'|' | xargs neutron subnet-delete
neutron net-list | grep private | cut -f2 -d'|' | xargs neutron net-delete
EOF
    chmod 755 $DEVSTACK_PATH/local.sh
fi
