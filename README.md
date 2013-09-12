elasticRecheck
==============

Idea
----
When a tempest job failure is detected, by monitoring gerrit (using gerritlib), a collection of logstash queries will be run on the failed job to detect what the bug was.

Eventually this can be tied into the rechecker tool and launchpad

Dependencies
------------
gerritlib
pyelasticsearch
