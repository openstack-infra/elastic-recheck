===============================
elastic-recheck
===============================

"Classify tempest-devstack failures using ElasticSearch"

* Open Source Software: Apache license
* Documentation: http://docs.openstack.org/developer/elastic-recheck

Idea
----
When a tempest job failure is detected, by monitoring gerrit (using
gerritlib), a collection of logstash queries will be run on the failed
job to detect what the bug was.

Eventually this can be tied into the rechecker tool and launchpad


queries/
--------

All queries are stored in separate yaml files in a queries directory
at the top of the elastic_recheck code base. The format of these files
is ######.yaml (where ###### is the bug number), the yaml should have
a ``query`` keyword which is the query text for elastic search.

Guidelines for good queries

- After a bug is resolved and has no more hits in elasticsearch, we
  should flag it with a resolved_at keyword. This will let us keep
  some memory of past bugs, and see if they come back. (Note: this is
  a forward looking statement, sorting out resolved_at will come in
  the future)
- Queries should get as close as possible to fingerprinting the root cause
- Queries should not return any hits for successful jobs, this is a
  sign the query isn't specific enough

In order to support rapidly added queries, it's considered socially
acceptable to +A changes that only add 1 new bug query, and to even
self approve those changes by core reviewers.


Adding Bug Signatures
---------------------

Most transient bugs seen in gate are not bugs in tempest associated
with a specific tempest test failure, but rather some sort of issue
further down the stack that can cause many tempest tests to fail.

#. Given a transient bug that is seen during the gate, go through the
   logs (logs.openstack.org) and try to find a log that is associated
   with the failure. The closer to the root cause the better.
#. Go to logstash.openstack.org and create an elastic search query to
   find the log message from step 1. To see the possible fields to
   search on click on an entry. Lucene query syntax is available at
   http://lucene.apache.org/core/4_0_0/queryparser/org/apache/lucene/queryparser/classic/package-summary.html#package_description
#. Add a comment to the bug with the query you identified and a link to
   the logstash url for that query search.
#. Add the query to ``elastic-recheck/queries/BUGNUMBER.yaml`` and push
   the patch up for review.
   https://git.openstack.org/cgit/openstack-infra/elastic-recheck/tree/queries


Future Work
------------

- Move config files into a separate directory
- Make unit tests robust
- Add debug mode flag
- Expand gating testing
- Cleanup and document code better
- Sort out resolved_at stamping to remove active bugs
- Move away from polling ElasticSearch to discover if its ready or not
- Add nightly job to propose a patch to remove bug queries that return
  no hits -- Bug hasn't been seen in 2 weeks and must be closed
- implement resolved_at in loader


Main Dependencies
------------------
- gerritlib
- pyelasticsearch
