.. _quickstart:

=====================
Developer Quick-Start
=====================

This is a quick walkthrough to get you started developing code for
networking-odl. This assumes you are already familiar with submitting code
reviews to an OpenStack project.

.. see also::

   https://docs.openstack.org/infra/manual/developers.html

Setup Dev Environment
=====================

Install OS-specific prerequisites::

    # Ubuntu/Debian 14.04:
    sudo apt-get update
    sudo apt-get install python-dev libssl-dev libxml2-dev curl \
                         libmysqlclient-dev libxslt1-dev libpq-dev git \
                         libffi-dev gettext build-essential

    # CentOS/RHEL 7.2:
    sudo yum install python-devel openssl-devel mysql-devel curl \
                     libxml2-devel libxslt-devel postgresql-devel git \
                     libffi-devel gettext gcc

    # openSUSE/SLE 12:
    sudo zypper --non-interactive install git libffi-devel curl \
                        libmysqlclient-devel libopenssl-devel libxml2-devel \
                        libxslt-devel postgresql-devel python-devel \
                        gettext-runtime

Install pip::

    curl -s https://bootstrap.pypa.io/get-pip.py | sudo python

Install common prerequisites::

    sudo pip install virtualenv flake8 tox testrepository git-review

You may need to explicitly upgrade virtualenv if you've installed the one
from your OS distribution and it is too old (tox will complain). You can
upgrade it individually, if you need to::

    sudo pip install -U virtualenv

Networking-odl source code should be pulled directly from git::

    # from your home or source directory
    cd ~
    git clone https://git.openstack.org/openstack/networking-odl
    cd networking-odl


For installation of networking-odl refer to :doc:`/install/index`.
For testing refer to :doc:`Testing <testing>` guide.

Verifying Successful Installation
==================================

There are some checks you can run quickly to verify that networking-odl
has been installed sucessfully.

#. Neutron agents must be in runing state, if you are using pseudo-agent
   for port binding then output of **openstack network agent list** should
   be something like::

      ubuntu@ubuntu-14:~/devstack$ openstack network agent list
      +----------------------------+----------------+-----------+-------------------+-------+-------+-----------------------------+
      | ID                         | Agent Type     | Host      | Availability Zone | Alive | State | Binary                      |
      +----------------------------+----------------+-----------+-------------------+-------+-------+-----------------------------+
      | 00628905-6550-43a5-9cda-   | ODL L2         | ubuntu-14 | None              | True  | UP    | neutron-odlagent-           |
      | 175a309ea538               |                |           |                   |       |       | portbinding                 |
      | 37491134-df2a-             | DHCP agent     | ubuntu-14 | nova              | True  | UP    | neutron-dhcp-agent          |
      | 45ab-8373-e186154aebee     |                |           |                   |       |       |                             |
      | 8e0e5614-4d68-4a42-aacb-   | Metadata agent | ubuntu-14 | None              | True  | UP    | neutron-metadata-agent      |
      | d0a10df470fb               |                |           |                   |       |       |                             |
      +----------------------------+----------------+-----------+-------------------+-------+-------+-----------------------------+

    Your output of this command may vary depending on the your environment,
    for example hostname etc.

#. You can check that opendaylight is running by executing following
     command::

       ubuntu@ubuntu-14:~/devstack$ ps -eaf | grep opendaylight



Launching Instance and floating IP
==================================

#. Gather paramters required for launching instance. We need flavor Id,
   image Id and network id, following comand can be used for launching an
   instance::

       openstack server create --flavor <flavor(m1.tiny)> --image \
       <image(cirros)> --nic net-id=<Network ID> --security-group \
       <security group(default) --key-name <keyname(mykey)> \
       <server name(test-instance)>

   For details on creating instances refer to [#third]_ and
   [#fourth]_.

#. Attaching floating IPs to created server can be done by following command::

     openstack server add floating ip <INSTANCE_NAME_OR_ID(test-instance) \
     <FLOATING_IP_ADDRESS(203.20.2.12)>

   For details on attaching floating IPs refer to [#fifth]_.


Useful Commands
================

#. For verifying status try following command::

       ubuntu@ubuntu-14:<Location of opendaylight directory>/distribution-karaf-0.6.0-SNAPSHOT/bin$ ./karaf status

   You should receive following output::

       Running ...

#. You can login using available client::

      ubuntu@ubuntu-14:<Location of opendaylight directory>/distribution-karaf-0.6.0-SNAPSHOT/bin$ ./client

   You will receive output in following format::

       Logging in as karaf
       3877 [sshd-SshClient[6dbb137d]-nio2-thread-3] WARN org.apache.sshd.client.keyverifier.AcceptAllServerKeyVerifier - Server at [/0.0.0.0:8101, RSA, 56:41:48:1c:38:3b:73:a8:a5:96:8e:69:a5:4c:93:e0] presented unverified {} key: {}
        ________                       ________                .__  .__       .__     __
        \_____  \ ______   ____   ____ \______ \ _____  ___.__.|  | |__| ____ |  |___/  |_
         /   |   \\____ \_/ __ \ /    \ |    |  \\__  \<   |  ||  | |  |/ ___\|  |  \   __\
        /    |    \  |_> >  ___/|   |  \|    `   \/ __ \\___  ||  |_|  / /_/  >   Y  \  |
        \_______  /   __/ \___  >___|  /_______  (____  / ____||____/__\___  /|___|  /__|
                \/|__|        \/     \/        \/     \/\/            /_____/      \/

       Hit '<tab>' for a list of available commands
       and '[cmd] --help' for help on a specific command.
       Hit '<ctrl-d>' or type 'system:shutdown' or 'logout' to shutdown OpenDaylight.

   Now you can run commands as per your for example::

        opendaylight-user@root>subnet-show
        No SubnetOpData configured.
        Following subnetId is present in both subnetMap and subnetOpDataEntry



        Following subnetId is present in subnetMap but not in subnetOpDataEntry

        Uuid [_value=2131f292-732d-4ba4-b74e-d70c07eceeb4]

        Uuid [_value=7a03e5d8-3adb-4b19-b1ec-a26691a08f26]

        Uuid [_value=7cd269ea-e06a-4aa3-bc11-697d71be4cbd]

        Uuid [_value=6da591bc-6bba-4c8a-a12b-671265898c4f]


        Usage 1: To display subnetMaps for a given subnetId subnet-show --subnetmap [<subnetId>]

        Usage 2: To display subnetOpDataEntry for a given subnetId subnet-show --subnetopdata [<subnetId>]

   To get help on some command::

        opendaylight-user@root>help feature
        COMMANDS
        info         Shows information about selected feature.
        install      Installs a feature with the specified name and version.
        list         Lists all existing features available from the defined repositories.
        repo-add     Add a features repository.
        repo-list    Displays a list of all defined repositories.
        repo-refresh Refresh a features repository.
        repo-remove  Removes the specified repository features service.
        uninstall    Uninstalls a feature with the specified name and version.
        version-list Lists all versions of a feature available from the currently available repositories.

   There are other helpfull commands, for example, log:tail, log:set, shutdown
   to get tail of logs, set log levels and shutdown.

   For checking neutron bundle is installed::

        opendaylight-user@root>feature:list -i | grep neutron
        odl-neutron-service                            | 0.8.0-SNAPSHOT   | x         | odl-neutron-0.8.0-SNAPSHOT                | OpenDaylight :: Neutron :: API
        odl-neutron-northbound-api                     | 0.8.0-SNAPSHOT   | x         | odl-neutron-0.8.0-SNAPSHOT                | OpenDaylight :: Neutron :: Northbound
        odl-neutron-spi                                | 0.8.0-SNAPSHOT   | x         | odl-neutron-0.8.0-SNAPSHOT                | OpenDaylight :: Neutron :: API
        odl-neutron-transcriber                        | 0.8.0-SNAPSHOT   | x         | odl-neutron-0.8.0-SNAPSHOT                | OpenDaylight :: Neutron :: Implementation
        odl-neutron-logger                             | 0.8.0-SNAPSHOT   | x         | odl-neutron-0.8.0-SNAPSHOT                | OpenDaylight :: Neutron :: Logger

   For checking netvirt bundle is installed::

        opendaylight-user@root>feature:list -i | grep netvirt
        odl-netvirt-api                                | 0.4.0-SNAPSHOT   | x         | odl-netvirt-0.4.0-SNAPSHOT                | OpenDaylight :: NetVirt :: api
        odl-netvirt-impl                               | 0.4.0-SNAPSHOT   | x         | odl-netvirt-0.4.0-SNAPSHOT                | OpenDaylight :: NetVirt :: impl
        odl-netvirt-openstack                          | 0.4.0-SNAPSHOT   | x         | odl-netvirt-0.4.0-SNAPSHOT                | OpenDaylight :: NetVirt :: OpenStack


#. For exploration of API's following links can be used::

         API explorer:
           http://localhost:8080/apidoc/explorer

         Karaf:
           http://localhost:8181/apidoc/explorer/index.html

   Detailed information can be found [#sixth]_.

.. rubric:: References

.. [#third] https://docs.openstack.org/mitaka/install-guide-rdo/launch-instance-selfservice.html
.. [#fourth] https://docs.openstack.org/draft/install-guide-rdo/launch-instance.html
.. [#fifth] https://docs.openstack.org/user-guide/cli-manage-ip-addresses.html
.. [#sixth] https://wiki.opendaylight.org/view/OpenDaylight_Controller:MD-SAL:Restconf_API_Explorer
