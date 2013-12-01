===========================
 Elastic Recheck Dashboard
===========================

Elastic Recheck is a handy tool for mining the data in our logstash
environment to categorize race conditions in the OpenStack gate. In
addition to including a number of command line tools, we provide an
html dashboard, because the kids love that html.

Architecture
============

The dashboard currently consists of static html and a set of
javascript libraries, which read json files full of data, and do
client side rendering of graphs. This may change in the future.

Below this tree you'll find a set of sub-directories that assume that
you are running this in an apache environment.

 - static files - /usr/share/elastic-recheck
 - dynamic json - /var/lib/elastic-recheck
 - apache config - /etc/apache/conf.d/elastic-recheck.conf

Json files directory is expected to be mapped to /elastic-recheck/data
and the static files to /elastic-recheck.

Installation
============

At install time for elastic-recheck the static files are installed as
per our assumed location. The apache configuration is not changed,
however an example is provided in the conf directory.
