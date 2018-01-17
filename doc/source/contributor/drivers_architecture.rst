ODL Drivers Architecture
========================

This document covers architectural concepts of the ODL drivers. Although
'driver' is an ML2 term, it's used widely in ODL to refer to any
implementation of APIs. Any mention of ML2 in this document is solely for
reference purposes.

V1 Driver Overview
------------------

The first driver version was a naive implementation which synchronously
mirrored all calls to the ODL controller. For example, a create network request
would first get written to the DB by Neutron's ML2 plugin, and then the ODL
driver would send the request to POST the network to the ODL controller.

Although this implementation is simple, it has a few problems:

* ODL is not really synchronous, so if the REST call succeeds it doesn't mean
  the action really happened on ODL.
* The "synchronous" call can be a bottleneck under load.
* Upon failure the V1 driver would try to "full sync" the entire Neutron DB
  over on the next call, so the next call could take a very long time.
* It doesn't really handle race conditions:

  - For example, create subnet and then create port could be sent in parallel
    by the driver in an HA Neutron environment, causing the port creation to
    fail.
  - Full-sync could possibly recreate deleted resources if the deletion happens
    in parallel.

.. _v2_design:

V2 Driver Design
----------------

The V2 driver set upon to tackle problems encountered in the V1 driver while
maintaining feature parity.
The major design concept of the V2 driver is *journaling* - instead of passing
the calls directly to the ODL controller, they get registered
in the journal table which keeps a sort of queue of the various operations that
occurred on Neutron and should be mirrored to the controller.

The journal is processed mainly by a journaling thread which runs periodically
and checks if the journal table has any entries in need of processing.
Additionally the thread is triggered in the postcommit hook of the operation
(where applicable).

If we take the example of create network again, after it gets stored in the
Neutron DB by the ML2 plugin, the ODL driver stores a "journal entry"
representing that operation and triggers the journalling thread to take care of
the entry.

The journal entry is recorded in the pre-commit phase (whenever applicable) so
that in case of a commit failure the journal entry gets aborted along with the
original operation, and there's nothing extra needed.

The *get_resources_for_full_sync* method is defined in the ResourceBaseDriver
class, it fetches all the resources needed for full sync, based on resource
type. To override the default behaviour of *get_resources_for_full_sync*
define it in driver class, For example

  #. L2 gateway driver needs to provide customized method for filtering of
     fetched gateway connection information from database. Neutron
     defines *l2_gateway_id* for a l2 gateway connection but ODL expects
     *gateway_id*, these kind of pre or post processing can be done in this
     method.
  #. For lbaas driver, as per default resource fetching mechanism, it looks for
     *get_member* instead the lbaas plugin defines *get_pool_member*, by
     overriding the *get_resources* method, it is possible to solve this
     inconsistency.

Journal Entry Lifecycle
-----------------------

The first state in which a journal entry is created is the 'pending' state. In
this state, the entry is awaiting a thread to pick it up and process it.
Multiple threads can try to grab the same journal entry, but only one will
succeed since the "selection" is done inside a 'select for update' clause.
Special care is taken for GaleraDB since it reports a deadlock if more than
one thread selects the same row simultaneously.

Once an entry has been selected it will be put into the 'processing' state
which acts as a lock. This is done in the same transaction so that in case
multiple threads try to "lock" the same entry only one of them will succeed.
When the winning thread succeeds it will continue with processing the entry.

The first thing the thread does is check for dependencies - if the entry
depends on another one to complete. If a dependency is found, the entry is put
back into the queue and the thread moves on to the next entry.

When there are no dependencies for the entry, the thread analyzes the operation
that occurred and performs the appropriate call to the ODL controller. The call
is made to the correct resource or collection and the type of call (PUT, POST,
DELETE) is determined by the operation type. At this point if the call was
successful (i.e. got a 200 class HTTP code) the entry is marked 'completed'.

In case of a failure the thread determines if this is an expected failure (e.g.
network connectivity issue) or an unexpected failure. For unexpected failures
a counter is raised, so that a given entry won't be retried more than a given
amount of times. Expected failures don't change the counter. If the counter
exceeds the configured amount of retries, the entry is marked as 'failed'.
Otherwise, the entry is marked back as 'pending' so that it can later be
retried.

Full Sync & Recovery
--------------------

.. code:: python

  file: networking_odl/journal/base_driver.py

  ALL_RESOURCES = {}

  class ResourceBaseDriver(object):
      # RESOURCES is dictionary of resource_type and resource_suffix to
      # be defined by the drivers class.
      RESOURCES = {}

      def __init__(self, plugin_type, *args, **kwargs):
          super(ResourceBaseDriver, self).__init__(*args, **kwargs)
          self.plugin_type = plugin_type
          # All the common methods to be used by full sync and recovery
          # specific to driver.

          # Only driver is enough for all the information. Driver has
          # plugin_type for fetching the information from db and resource
          # suffix is available through driver.RESOURCES.
          for resource, resource_suffix in self.RESOURCES.items():
              ALL_RESOURCES[resource] = self

      def get_resource_for_recovery(self, resource_type, resource_id):
          # default definition to be used, if get_resource method is not
          # defined then this method gets called by recovery

      def get_resources_for_full_sync(self, resource_type):
          # default definition to be used, if get_resources method is not
          # defined then this method gets called by full sync

      @staticmethod
      def get_method_name_by_resource_suffix(method_suffix):
          # Returns method name given resource suffix

      @staticmethod
      def get_method(plugin, method_name):
          # Returns method for a specific plugin

  file: networking_odl/<driver-name>/<driver-file>.py

  class XXXXDriver(ResourceBaseDriver, XXXXDriverBase):
      RESOURCES = {
          odl_const.XXXX: odl_const.XXXY,
          odl_const.XXXY: odl_const.XXYY
      }

      def __init__(self, *args, **kwargs):
          super(XXXXDriver, self)(plugin_type, *args, **kwargs)
          # driver specific things

      # get_resources_for_full_sync and get_resource_for_recovery methods are
      # optional and they have to be defined, if customized behaviour is
      # required. If these methods are not defined in the driver then default
      # methods defined in ResourceBaseDriver is used.
      def get_resources_for_full_sync(self, resource_type):
          # returns resource for full sync

      def get_resource_for_recovery(self, resource_type, resource_id):
          # returns resource for recovery
