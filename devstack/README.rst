======================
 Enabling in Devstack
======================

1. Download DevStack

2. Add this repo as an external repository::

     > cat local.conf
     [[local|localrc]]
     enable_plugin networking-odl https://github.com/stackforge/networking-odl
     enable_service odl-compute odl-server


3. run ``stack.sh``
