#!/usr/bin/env bash

set -xe

NETWORKING_ODL_DIR="$BASE/new/networking-odl"
SCRIPTS_DIR="/usr/os-testr-env/bin/"
GATE_STACK_USER=stack

venv=${1:-"dsvm-functional"}

function generate_testr_results {
    # Give job user rights to access tox logs
    sudo -H -u $owner chmod o+rw .
    sudo -H -u $owner chmod o+rw -R .testrepository
    if [ -f ".testrepository/0" ] ; then
        .tox/$venv/bin/subunit-1to2 < .testrepository/0 > ./testrepository.subunit
        $SCRIPTS_DIR/subunit2html ./testrepository.subunit testr_results.html
        gzip -9 ./testrepository.subunit
        gzip -9 ./testr_results.html
        sudo mv ./*.gz /opt/stack/logs/
    fi
}

case $venv in
    dsvm-functional*|dsvm-fullstack)
        owner=$GATE_STACK_USER
        sudo_env=

        # Set owner permissions according to job's requirements.
        cd $NETWORKING_ODL_DIR
        sudo chown -R $owner:stack $NETWORKING_ODL_DIR

        # Run tests
        echo "Running networking-odl $venv test suite"
        set +e
        sudo -H -u $owner $sudo_env tox -e $venv
        testr_exit_code=$?
        set -e

        # Collect and parse results
        generate_testr_results
        exit $testr_exit_code
        ;;
    *)
        echo "Unrecognized test suite $venv".
        exit 1
esac
