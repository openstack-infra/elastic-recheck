===============================
elastic-recheck
===============================

"Classify tempest-devstack failures using ElasticSearch"

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/elastic-recheck

Idea
----
When a tempest job failure is detected, by monitoring gerrit (using
gerritlib), a collection of logstash queries will be run on the failed
job to detect what the bug was.

Eventually this can be tied into the rechecker tool and launchpad


queries/
------------

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
