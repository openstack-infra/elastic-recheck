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
- Make unit tests robust

Dependencies
------------
- gerritlib
- pyelasticsearch
