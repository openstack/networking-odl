echo "*********************************************************************"
echo "Begin $0"
echo "*********************************************************************"

set -o xtrace

# Set for DevStack compatibility

source $GRENADE_DIR/grenaderc
source $TARGET_DEVSTACK_DIR/stackrc

# Get functions from current DevStack
source $TARGET_DEVSTACK_DIR/inc/python

NETWORKING_ODL_DIR="$TARGET_RELEASE_DIR/networking-odl"

setup_develop $NETWORKING_ODL_DIR

set +x
set +o xtrace
echo "*********************************************************************"
echo "SUCCESS: End $0"
echo "*********************************************************************"
