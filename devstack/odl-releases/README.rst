=======================
ODL release definitions
=======================

This directory contains definitions for OpenDaylight releases so that
devstack can determine the URI for ODL distribution to download.


Examples
========
Even when not full version is specified, it downloads maven metadata
and determine latest version. Now devstack scripts is smart to guess
URI based on release name and version which can be deduced from its
filename. So for typical cases, empty file will do.


Release boron-0.5.1::

  export ODL_BUNDLEVERSION='0.5.1-Boron'
  export ODL_NAME=distribution-karaf-${BUNDLEVERSION}
  ODL_REQUIRED_JAVA_VERSION=${ODL_REQUIRED_JAVA_VERSION:-8}


SR Release boron-0.5.1-SR1::

  export ODL_BUNDLEVERSION='0.5.1-Boron-SR1'
  export ODL_NAME=distribution-karaf-${BUNDLEVERSION}
  ODL_REQUIRED_JAVA_VERSION=${ODL_REQUIRED_JAVA_VERSION:-8}


snapshot beryllium-snapshot-0.4.2::

  BUNDLEVERSION='0.4.2-SNAPSHOT'
  ODL_SNAPSHOT_VERSION=${ODL_SNAPSHOT_VERSION:-latest}
  export ODL_NAME=distribution-karaf-${BUNDLEVERSION}
  ODL_REQUIRED_JAVA_VERSION=${ODL_REQUIRED_JAVA_VERSION:-8}


latest snapshot without revision boron-snapshot-0.5::

  ODL_SNAPSHOT_VERSION=${ODL_SNAPSHOT_VERSION:-latest}
  ODL_REQUIRED_JAVA_VERSION=${ODL_REQUIRED_JAVA_VERSION:-8}


latest snapshot latest-snapshot::

  ODL_SNAPSHOT_VERSION=${ODL_SNAPSHOT_VERSION:-latest}
  ODL_REQUIRED_JAVA_VERSION=${ODL_REQUIRED_JAVA_VERSION:-8}


RC carbon-0.6.2-SR2-RC::

  ODL_BUNDLEVERSION='0.6.2-Carbon'
  NEXUSPATH="${ODL_URL_PREFIX}/content/repositories/autorelease-1929/org/opendaylight/integration/distribution-karaf/"


RC nitroge-0.7.0-RC3::

  ODL_BUNDLEVERSION="0.7.0"
  NEXUSPATH="${ODL_URL_PREFIX}/content/repositories/autorelease-1963/org/opendaylight/integration/karaf/"

