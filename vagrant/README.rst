=======
Vagrant
=======

  Devstack with Vagrant is to used to deploy OpenStack with ODL.

Setup Proxy(Optional)
---------------------

  If your network is behind a firwall, you can update SOCKS5_IP/SOCKS5_PORT and
  run ./setup_proxy.sh.

Vagrant Setup
-------------

# sudo apt-get install virtualbox
# wget --no-check-certificate https://releases.hashicorp.com/vagrant/1.8.6/vagrant_1.8.6_x86_64.deb
# sudo dpkg -i vagrant_1.8.6_x86_64.deb

Vagrant Cleanup
---------------

vagrant destroy -f


Integration
-----------

.. include:: ../../../vagrant/integration/multinode/README.rst
