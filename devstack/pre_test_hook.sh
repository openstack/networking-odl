#!/usr/bin/env bash

set -xe

# Drop a token that marks the build as coming from openstack infra
GATE_DEST=$BASE/new
DEVSTACK_PATH=$GATE_DEST/devstack

case "$ODL_RELEASE_BASE" in
    beryllium-snapshot)
        ODL_RELEASE=beryllium-snapshot-0.4.0
        ;;
    lithium-snapshot)
        ODL_RELEASE=lithium-snapshot-0.3.3
        ;;
    *)
        # for compatibility before updating
        # project-config/jenkins/jobs/networking-odl.yaml
        ODL_RELEASE=lithium-snapshot-0.3.3
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
