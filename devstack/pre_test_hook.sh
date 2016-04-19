#!/usr/bin/env bash

set -xe

# Drop a token that marks the build as coming from openstack infra
GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

case "$ODL_RELEASE_BASE" in
    boron-snapshot)
        ODL_RELEASE=boron-snapshot-0.5.0
        ;;
    beryllium-snapshot)
        ODL_RELEASE=beryllium-snapshot-0.4.2
        ;;
    lithium-snapshot)
        ODL_RELEASE=lithium-snapshot-0.3.5
        ;;
    *)
        echo "Unknown ODL release base: $ODL_RELEASE_BASE"
        exit 1
        ;;
esac

cat <<EOF >> $DEVSTACK_PATH/localrc

IS_GATE=True

# Set here the ODL release to use for the Gate job
ODL_RELEASE=${ODL_RELEASE}

# Switch to using the ODL's L3 implementation
ODL_L3=True

# Enable debug logs for odl ovsdb
ODL_NETVIRT_DEBUG_LOGS=True

EOF
