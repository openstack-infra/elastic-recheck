===============================
elastic-recheck
===============================

"Use ElasticSearch to classify OpenStack gate failures"

* Open Source Software: Apache license

Idea
----
Identifying the specific bug that is causing a transient error in the gate
is very hard. Just identifying which tempest test failed is not enough
because a single bug can potentially cause multiple tempest tests to fail.
If we can find a fingerprint for a specific bug using logs, then we can use
ElasticSearch to automatically detect any occurrences of the bug.

Using these fingerprints elastic-recheck can:

* Search ElasticSearch for all occurrences of a bug.
* Identify bug trends such as: when it started, is the bug fixed, is it
  getting worse, etc.
* Classify bug failures in real time and report back to gerrit if we find a
  match, so a patch author knows why the test failed.

queries/
--------

All queries are stored in separate yaml files in a queries directory
at the top of the elastic-recheck code base. The format of these files
is ######.yaml (where ###### is the launchpad bug number), the yaml should have
a ``query`` keyword which is the query text for elastic search.

Guidelines for good queries

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

   Note that queries can only be written against INFO level and higher log
   messages. This is by design to not overwhelm the search cluster.

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
- Add ability to check if any resolved bugs return
- Move away from polling ElasticSearch to discover if its ready or not
- Add nightly job to propose a patch to remove bug queries that return
  no hits -- Bug hasn't been seen in 2 weeks and must be closed
