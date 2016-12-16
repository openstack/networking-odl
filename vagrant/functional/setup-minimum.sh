#!/bin/bash -xe
#
# Script to install minimum environment to run reproduce.sh
#

# install pre required packages
apt-get install --yes python-pip
pip install --upgrade pip
pip install --upgrade setuptools
pip install --upgrade virtualenv
pip install --upgrade tox
