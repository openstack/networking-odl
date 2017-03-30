..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

================================
Dependency Validations on Create
================================

https://blueprints.launchpad.net/networking-odl/+spec/dep-validations-on-create

Right now V2 driver entry dependency validations happen when a journal entry is
picked for processing. This spec proposes that this be moved to entry creation
time, in order to have a clear understanding of the entry dependencies and
conserve journal resources.


Problem Description
===================

Dependency validations are necessary in the V2 driver because each operation
gets recorded in a journal entry and sent to ODL asynchronously. Thus, a
consecutive operation might be sent to ODL before the first one finishes, while
relying on the first operation.
For example, when a subnet gets created it references a network, but if the
network was created right before the subnet was then the subnet create
shouldn't be sent over until the network create was sent.

Currently these checks are performed each time an entry is selected for
processing - if the entry passes the dependency checks then it gets processed
and if the dependency check fails (i.e. finds a previous unhandled entry that
needs to execute before this one) then the entry gets sent back to the queue.

Generally this is not optimal for several reasons:
 * No clear indication of relations between the entries.

   * The logic is hidden in the code and there's no good way to know why an
     entry fails a dependency check.
   * Difficult to debug in case of problems.
   * Difficult to spot phenomenon such as a cyclic dependency.

 * Wasted CPU effort.

   * An entry can be checked multiple times for dependencies.
   * Lots of redundant DB queries to determine dependencies each time.


Proposed Change
===============

The proposed solution is to move the dependency calculation to entry creation
time.

When a journal entry is created the dependency management system will calculate
the dependencies on other entries (Similarly to how it does now) and if there
are journal entries the new entry should depend on, their IDs will be inserted
into a link table.

Thus, when the journal looks for an entry to pick up it will only look for
entries that no other entry depends on by making sure there aren't any entries
in the dependency table.

When a journal entry is done processing (either successfully or reaches failed
state), the dependency links will be removed from the dependency table so that
dependent rows can be processed.

The proposed table::

   +------------------------+
   | odl_journal_dependency |
   +------------------------+
   | parent_id              |
   | dependent_id           |
   +------------------------+

The table columns will be foreign keys to the seqnum column in the journal
table. The constraints will be defined as "ON DELETE CASCADE" so that when a
journal entry is removed any possible rows will be removed as well.
The primary key will be made from both columns of the table as this is a link
table and not an actual entity.
If we face DB performance issues (highly unlikely, since this table should
normally have a very small amount of rows if any at all) then an index can be
constructed on the dependent_id column.

The dependency management mechanism will locate parent entries for the given
entry and will populate the table so that the parent entry's seqnum will be
set as the parent_id, and the dependent entry id will be set as dependent_id.
When the journal picks up an entry for processing it will condition it on not
having any rows with the parent_id in the dependency table. This will ensure
that dependent rows get handled after the parent rows have finished processing.


Performance Considerations
==========================

Generally the performance shouldn't be impacted as we're moving the part of
code that does dependency calculations from the entry selection time to entry
creation time. This will assure that dependency calculations happen only once
per journal entry.

However, some simple benchmarks should be performed before & after the change:
 * Average Tempest run time.
 * Average CPU consumption on Tempest.
 * Full sync run time (Start to finish of all entries).

If performance suffers a severe degradation then we should consider
alternative solutions.


Questions
=========

Q: Should entries in "failed" state block other entries?

A: Currently "failed" rows are not considered as blocking for dependency
   validations, but we might want to change this as it makes little sense to
   process a dependent entry that failed processing.

Q: How will this help debug-ability?

A: It will be easy to query the table contents at any time to figure out which
   entries depend on which other entries.

Q: How will we be able to spot cyclic dependencies?

A: Currently this isn't planned as part of the spec, but a DB query (or a
   series of them) can help determine if this problem exists.

