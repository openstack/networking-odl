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

source $NETWORKING_ODL_DIR/devstack/entry_points
install_networking_odl

set +x
set +o xtrace
echo "*********************************************************************"
echo "SUCCESS: End $0"
echo "*********************************************************************"
