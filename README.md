elasticRecheck
==============

Classify tempest-devstack failures using a list of elastic search queries.

Idea
----
When a tempest job failure is detected, by monitoring gerrit (using gerritlib), a collection of logstash queries will be run on the failed job to detect what the bug was.

Eventually this can be tied into the rechecker tool and launchpad

Future Work
------------
- Pull in list of queries from a more flexible source, so a commit isn't needed to update each time
- Make unit tests robust and not need internet
- Write tests to validate queries.json
- Use cookiecutter to clean this repo up

Dependencies
------------
- gerritlib
- pyelasticsearch
