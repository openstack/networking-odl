#!/usr/bin/env bash

set -xe

NETWORKING_ODL_DIR="${NETWORKING_ODL_DIR:-$BASE/new/networking-odl}"
SCRIPTS_DIR="/usr/os-testr-env/bin/"
GATE_STACK_USER=stack
OS_LOG_PATH=${OS_LOG_PATH:-$BASE/logs}

venv=${1:-"dsvm-functional"}

function _odl_show_info {
    local VENV=$1
    local OVS_DUMP
    case $VENV in
        dsvm-fullstack*)
            OVS_DUMP=True
            ;;
        *)
            # in case functional test case, ovs isn't installed
            OVS_DUMP=False
            ;;
    esac

    sudo ip address
    sudo ip link
    sudo ip route
    if [[ "$OVS_DUMP" == "True" ]]; then
        sudo ovsdb-client dump
        sudo ovs-vsctl show
        for br in $(sudo ovs-vsctl list-br); do
            echo "--- flows on $br ---"
            sudo ovs-ofctl --protocols OpenFlow13 dump-ports $br
            sudo ovs-ofctl --protocols OpenFlow13 dump-ports-desc $br
            sudo ovs-ofctl --protocols OpenFlow13 dump-flows $br
            sudo ovs-ofctl --protocols OpenFlow13 dump-groups $br
            sudo ovs-ofctl --protocols OpenFlow13 dump-group-stats $br
        done
    fi

    # ODL_UESRNAME=admin
    # ODL_PASSWORD=admin
    # ODL_MGR_HOST=$SERVICE_HOST
    # ODL_PORT=8087
    # There is no good way to retrieve from setting.odl at the moment
    local PATHES="config/neutron:neutron"
    if [[ "$OVS_DUMP" == "True" ]]; then
        PATHES="$PATHES config/opendaylight-inventory:nodes config/elan:elan-instances config/elan:elan-interfaces"
    fi
    for path in $PATHES; do
        echo "path=${path}"
        curl --silent --user admin:admin "http://localhost:8087/restconf/${path}?prettyPrint=true"
        echo
    done
    echo
    echo
}

function generate_testr_results {
    # Give job user rights to access tox logs
    sudo -H -u $owner chmod o+rw .
    sudo -H -u $owner chmod o+rw -R .stestr
    if [ -f ".stestr/0" ] ; then
        # Some tests have python-subunit installed globally
        # and in gate we specified sitepackages=True
        if [ -x .tox/$venv/bin/subunit-1to2 ]; then
            SUBUNIT1TO2=.tox/$venv/bin/subunit-1to2
        else
            # Use system subunit-1to2
            SUBUNIT1TO2=subunit-1to2
        fi
        $SUBUNIT1TO2 < .stestr/0 > ./stestr.subunit
        $SCRIPTS_DIR/subunit2html ./stestr.subunit testr_results.html
        gzip -9 ./stestr.subunit
        gzip -9 ./testr_results.html
        sudo mv ./*.gz /opt/stack/logs/
    fi
}

case $venv in
    dsvm-functional*|dsvm-fullstack*)
        owner=$GATE_STACK_USER
        sudo_env="ODL_RELEASE_BASE=${ODL_RELEASE_BASE}"

        # Set owner permissions according to job's requirements.
        sudo chown -R $owner:stack $BASE/new
        cd $NETWORKING_ODL_DIR
        if [[ -n "$OS_LOG_PATH" ]]; then
            sudo mkdir -p $OS_LOG_PATH
            sudo chown -R $owner:stack $OS_LOG_PATH
        fi

        echo "odl info before tests"
        _odl_show_info $venv
        $BASE/new/opendaylight/*karaf-*/bin/client "feature:list -i"

        # Run tests
        echo "Running networking-odl $venv test suite"
        set +e
        sudo -H -u $owner $sudo_env tox -e $venv
        testr_exit_code=$?
        set -e

        echo "odl info after tests"
        _odl_show_info $venv

        # stop ODL server for complete log
        $BASE/new/opendaylight/*karaf-*/bin/stop
        sleep 3

        # Collect and parse results
        generate_testr_results
        exit $testr_exit_code
        ;;
    *)
        echo "Unrecognized test suite $venv".
        exit 1
esac
