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

Guidelines for good queries:

- Queries should get as close as possible to fingerprinting the root cause. A
  filename query is typically better than a console one, as that's matching a
  deep failure versus a surface symptom.

- Queries should not return any hits for successful jobs, this is a
  sign the query isn't specific enough. A rule of thumb is > 10% success hits
  probably means this isn't good enough.

- If it's impossible to build a query to target a bug, consider patching the
  upstream program to be explicit when it fails in a particular way.

- Use the 'tags' field rather than the 'filename' field for filtering. This is
  primarily because of grenade jobs where the same log file shows up in the
  'old' and 'new' side of the grenade job. For example, tags:"screen-n-cpu.txt"
  will query in logs/old/screen-n-cpu.txt and logs/new/screen-n-cpu.txt. The
  tags:"console" filter is also used to query in console.html as well as
  tempest and devstack logs.

- Avoid the use of wildcards in queries since they can put an undue burden on
  the query engine. A common case where wildcards would be useful are in
  querying against a specific set of build_name fields, e.g. gate-nova-python26
  and gate-nova-python27. Rather than use build_name:gate-nova-python*, list
  the jobs with an OR, e.g.:

  ::

   (build_name:"gate-nova-python26" OR build_name:"gate-nova-python27")

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
