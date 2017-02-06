Journal Maintenance
===================

Overview
--------

The V2 ODL driver is Journal based [#]_, which means that there's a journal of
entries detailing the various operations done on a Neutron resource.
The driver has a thread which is in charge of processing the journal of
operations which entails communicating the operation forward to the ODL
controller.

The journal entries can wind up in several states due to various reasons:

* PROCESSING - Stale lock left by a thread due to thread dying or other error
* COMPLETED - After the operation is processed successfully
* FAILED - If there was an unexpected error during the operation

These journal entries need to be dealt with appropriately, hence a maintenance
thread was introduced that takes care of journal maintenance and other related
tasks.
This thread runs in a configurable interval and is HA safe using a shared state
kept in the DB.

Currently the maintenance thread performs:

* Stale lock release
* Completed entries clean up
* Failed entries are handled by the recovery mechanism
* Full sync detect when ODL is "tabula rasa" and syncs all the resources to it

Creating New Maintenance Operations
-----------------------------------

Creating a new maintenance operation is as simple as writing a function
that receives the database session object and registering it using a call to::

  MaintenanceThread.register_operation

The best place to do so would be at the _start_maintenance_thread method of
the V2 OpenDaylightMechanismDriver class.

.. [#] See :ref:`v2_design` for details.

