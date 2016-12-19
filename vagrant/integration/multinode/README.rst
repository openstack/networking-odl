=======
vagrant
=======

  It is verified to work in the env:
    Host: Ubuntu 16.04 desktop 64bit with 16G memory & 256G disk
    Vagrant: 1.8.6
    Virtualbox: 5.0.24

OpenStack Setup
---------------

download primary & subnode configuration from jenkins log. example:
# curl http://logs.openstack.org/22/408422/1/check/gate-tempest-dsvm-networking-odl-multinode-carbon-snapshot-nv/ef988ee/logs/localrc.txt.gz > control.conf
# curl http://logs.openstack.org/22/408422/1/check/gate-tempest-dsvm-networking-odl-multinode-carbon-snapshot-nv/ef988ee/logs/subnode-2/localrc.txt.gz  > compute.conf
# vagrant up

Note: we already include control.conf & compute.conf in this example.

Run Tempest
-----------

# vagrant ssh control
# cd tempest
# tempest run --regex tempest.scenario.test_network_basic_ops.TestNetworkBasicOps.test_mtu_sized_frames
