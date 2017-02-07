..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

================
Journal Recovery
================

https://blueprints.launchpad.net/networking-odl/+spec/journal-recovery

Journal entries in the failed state need to be handled somehow. This spec will
try to address the issue and propose a solution.

Problem Description
===================

Currently there is no handling for Journal entries that reach the failed state.
A journal entry can reach the failed state for several reasons, some of which
are:

* Reached maximum failed attempts for retrying the operation.

* Inconsistency between ODL and the Neutron DB.

  * For example: An update fails because the resource doesn't exist in ODL.

* Bugs that can lead to failure to sync up.

These entries will be left in the journal table forever which is a bit wasteful
since they take up some space on the DB storage and also affect the performance
of the journal table.
Albeit each entry has a negligble effect on it's own, the impact of a large
number of such entries can become quite significant.

Proposed Change
===============

A "journal recovery" routine will run as part of the current journal
maintenance process.
This routine will scan the journal table for rows in the "failed" state and
will try to sync the resource for that entry.

The procedure can be best described by the following flow chart:

asciiflow::

  +-----------------+
  | For each entry  |
  | in failed state |
  +-------+---------+
          |
  +-------v--------+
  | Query resource |
  | on ODL (REST)  |
  +-----+-----+----+
        |     |                          +-----------+
     Resource |                          | Determine |
     exists   +--Resource doesn't exist--> operation |
        |                                | type      |
  +-----v-----+                          +-----+-----+
  | Determine |                                |
  | operation |                                |
  | type      |                                |
  +-----+-----+                                |
        |              +------------+          |
        +--Create------> Mark entry <--Delete--+
        |              | completed  |          |
        |              +----------^-+       Create/
        |                         |         Update
        |                         |            |
        |          +------------+ |      +-----v-----+
        +--Delete--> Mark entry | |      | Determine |
        |          | pending    | |      | parent    |
        |          +---------^--+ |      | relation  |
        |                    |    |      +-----+-----+
  +-----v------+             |    |            |
  | Compare to +--Different--+    |            |
  | resource   |                  |            |
  | in DB      +--Same------------+            |
  +------------+                               |
                                               |
  +-------------------+                        |
  | Create entry for  <-----Has no parent------+
  | resource creation |                        |
  +--------^----------+                  Has a parent
           |                                   |
           |                         +---------v-----+
           +------Parent exists------+ Query parent  |
                                     | on ODL (REST) |
                                     +---------+-----+
  +------------------+                         |
  | Create entry for <---Parent doesn't exist--+
  | parent creation  |
  +------------------+

For every error during the process the entry will remain in failed state but
the error shouldn't stop processing of further entries.


The implementation could be done in two phases where the parent handling is
done in a second phase.
For the first phase if we detect an entry that is in failed for a create/update
operation and the resource doesn't exist on ODL we create a new "create
resource" journal entry for the resource.

This proposal utilises the journal mechanism for it's operation while the only
part that deviates from the standard mode of operation is when it queries ODL
directly. This direct query has to be done to get ODL's representation of the
resource.

Performance Impact
------------------

The maintenance thread will have another task to handle. This can lead to
longer processing time and even cause the thread to skip an iteration.
This is not an issue since the maintenance thread runs in parallel and doesn't
directly impact the responsiveness of the system.

Since most operations here involve I/O then CPU probably won't be impacted.

Network traffic would be impacted slightly since we will attempt to fetch the
resource each time from ODL and we might attempt to fetch it's parent.
This is however negligble as we do this only for failed entries, which are
expected to appear rarely.


Alternatives
------------

The partial sync process could make this process obsolete (along with full
sync), but it's a far more complicated and problematic process.
It's better to start with this process which is more lightweight and doable
and consider partial sync in the future.


Assignee(s)
===========

Primary assignee:
  mkolesni <mkolesni@redhat.com>

Other contributors:
  None


References
==========

https://goo.gl/IOMpzJ

