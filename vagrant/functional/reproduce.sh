#!/bin/bash -xe
#
# Script to reproduce devstack-gate run.
#
# Prerequisites:
# - Fresh install of current Ubuntu LTS, with basic internet access.
#   Note we can and do run devstack-gate on other distros double check
#   where your job ran (will be recorded in console.html) to reproduce
#   as accurately as possible.
# - Must have python-all-dev, build-essential, git, libssl-dev installed
#   from apt, or their equivalents on other distros.
# - Must have virtualenv installed from pip
# - Must be run as root
#

exec 0</dev/null

declare -x DEVSTACK_GATE_TEMPEST_ALL="0"
declare -x DEVSTACK_GATE_TEMPEST_FULL="0"
declare -x DEVSTACK_GATE_TEMPEST_ALL_PLUGINS="0"
declare -x ZUUL_PROJECT="openstack/networking-odl"
declare -x DEVSTACK_GATE_IRONIC_BUILD_RAMDISK="1"
declare -x DEVSTACK_GATE_SAHARA="0"
declare -x DEVSTACK_LOCAL_CONFIG="enable_plugin networking-odl https://git.openstack.org/openstack/networking-odl
HOST_IP=127.0.0.1
UNSTACK_KEEP_ODL=True"
declare -x DEVSTACK_GATE_TEMPEST_NOTESTS="0"
declare -x DEVSTACK_CINDER_SECURE_DELETE="0"
declare -x DEVSTACK_GATE_SMOKE_SERIAL="0"
declare -x DEVSTACK_PROJECT_FROM_GIT=""
declare -x DEVSTACK_GATE_IRONIC_DRIVER="pxe_ssh"
declare -x OVERRIDE_ZUUL_BRANCH="master"
declare -x ZUUL_BRANCH="master"
declare -x DEVSTACK_GATE_SETTINGS="/opt/stack/new/networking-odl/devstack/devstackgaterc"
declare -x ZUUL_VOTING="0"
declare -x ZUUL_URL="http://zm06.openstack.org/p"
declare -x DEVSTACK_GATE_PROJECTS_OVERRIDE=""
declare -x DEVSTACK_CINDER_VOLUME_CLEAR="none"
declare -x DEVSTACK_GATE_FEATURE_MATRIX="features.yaml"
declare -x DEVSTACK_GATE_TEMPEST="0"
declare -x DEVSTACK_GATE_UNSTACK="1"
declare -x ZUUL_CHANGE="408294"
declare -x TOX_TESTENV_PASSENV="ZUUL_PIPELINE ZUUL_UUID ZUUL_VOTING ZUUL_CHANGE_IDS ZUUL_PATCHSET ZUUL_BRANCH ZUUL_REF ZUUL_COMMIT ZUUL_URL ZUUL_CHANGE ZUUL_CHANGES ZUUL_PROJECT"
declare -x DEVSTACK_GATE_INSTALL_TESTONLY="1"
declare -x DEVSTACK_GATE_TOPOLOGY="aio"
declare -x DEVSTACK_GATE_NETCONSOLE=""
declare -x DEVSTACK_GATE_NOVA_API_METADATA_SPLIT="0"
declare -x DEVSTACK_GATE_NEUTRON_DVR="0"
declare -x DEVSTACK_GATE_TIMEOUT="120"
declare -x DEVSTACK_GATE_CELLS="0"
declare -x DEVSTACK_GATE_MQ_DRIVER="rabbitmq"
declare -x DEVSTACK_GATE_REMOVE_STACK_SUDO="0"
declare -x DEVSTACK_GATE_TEMPEST_HEAT_SLOW="0"
declare -x DEVSTACK_GATE_IRONIC="0"
declare -x DEVSTACK_GATE_CLEAN_LOGS="1"
declare -x DEVSTACK_GATE_TEMPEST_DISABLE_TENANT_ISOLATION="0"
declare -x DEVSTACK_GATE_CEILOMETER_BACKEND="mysql"
declare -x ZUUL_CHANGES="openstack/networking-odl:master:refs/changes/94/408294/1"
declare -x DEVSTACK_GATE_EXERCISES="0"
declare -x DEVSTACK_GATE_VIRT_DRIVER="libvirt"
declare -x DEVSTACK_GATE_TROVE="0"
declare -x DEVSTACK_GATE_TEMPEST_LARGE_OPS="0"
declare -x DEVSTACK_GATE_ZEROMQ="0"
declare -x DEVSTACK_GATE_POSTGRES="0"
declare -x DEVSTACK_GATE_TIMEOUT_BUFFER="10"
declare -x ZUUL_REF="refs/zuul/master/Z8054bc24de3e47bd85ab550e02465160"
declare -x ZUUL_CHANGE_IDS="408294,1"
declare -x DEVSTACK_GATE_LIBVIRT_TYPE="qemu"
declare -x DEVSTACK_GATE_TEMPEST_STRESS_ARGS=""
declare -x DEVSTACK_GATE_TEMPEST_STRESS="0"
declare -x DEVSTACK_GATE_TEMPEST_REGEX=""
declare -x DEVSTACK_GATE_GRENADE=""
declare -x DEVSTACK_GATE_NEUTRON="1"
declare -x DEVSTACK_GATE_CONFIGDRIVE="0"
declare -x ZUUL_PIPELINE="check"
declare -x ZUUL_COMMIT="fd975d87091843d6b3bddec69654ba5c5a707ba7"
declare -x ZUUL_PATCHSET="1"
declare -x DEVSTACK_GATE_REQS_INTEGRATION="0"
declare -x ZUUL_UUID="86deca87c8af4cd3830520d95f20cd26"
declare -x PROJECTS="openstack/networking-odl "

pre_test_hook ()
{
    . $BASE/new/networking-odl/devstack/pre_test_hook.sh
}
declare -fx pre_test_hook
gate_hook ()
{
    bash -xe $BASE/new/networking-odl/networking_odl/tests/contrib/gate_hook.sh dsvm-functional
}
declare -fx gate_hook
post_test_hook ()
{
    bash -xe $BASE/new/networking-odl/networking_odl/tests/contrib/post_test_hook.sh dsvm-functional
}
declare -fx post_test_hook

# twist variables to install only necessary packages/projects
# it overrides pre_test_hook, gate_hook, post_test_hook and
# several variables.
source /home/vagrant/networking-odl/vagrant/functional/config-override.sh

mkdir -p workspace/
cd workspace/
export WORKSPACE=`pwd`

if [[ ! -e /usr/zuul-env ]]; then
    virtualenv /usr/zuul-env
    /usr/zuul-env/bin/pip install zuul
fi

cat > clonemap.yaml << IEOF
clonemap:
  - name: openstack-infra/devstack-gate
    dest: devstack-gate
IEOF

/usr/zuul-env/bin/zuul-cloner -m clonemap.yaml --cache-dir /opt/git https://git.openstack.org openstack-infra/devstack-gate

cp devstack-gate/devstack-vm-gate-wrap.sh ./safe-devstack-vm-gate-wrap.sh
./safe-devstack-vm-gate-wrap.sh
