===============================
elastic-recheck
===============================

"Classify tempest-devstack failures using ElasticSearch"

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/elastic-recheck

Idea
----
When a tempest job failure is detected, by monitoring gerrit (using gerritlib), a collection of logstash queries will be run on the failed job to detect what the bug was.

Eventually this can be tied into the rechecker tool and launchpad

Future Work
------------
- Move config files into a separate directory
- Make unit tests robust
- Merge both binaries
- Add debug mode flag
- Split out queries repo
- Expand gating testing
- Cleanup and document code better
- Move away from polling ElasticSearch to discover if its ready or not
- Add nightly job to propose a patch to remove bug queries that return no hits -- Bug hasn't been seen in 2 weeks and must be closed

Main Dependencies
------------------
- gerritlib
- pyelasticsearch
