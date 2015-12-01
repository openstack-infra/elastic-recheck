#!/usr/bin/env python

# Copyright 2013 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import ConfigParser
from datetime import datetime
import json
import os
import sys

from launchpadlib import launchpad
import pytz
import requests

try:
    # Disable InsecurePlatformWarning warnings as documented here
    # https://github.com/kennethreitz/requests/issues/2214
    from requests.packages.urllib3.exceptions import InsecurePlatformWarning
    requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)
except ImportError:
    # If there's an import error, then urllib3 may be packaged
    # separately, so apply it there too
    import urllib3
    from urllib3.exceptions import InsecurePlatformWarning
    urllib3.disable_warnings(InsecurePlatformWarning)

import elastic_recheck.elasticRecheck as er
from elastic_recheck import log as logging
import elastic_recheck.query_builder as qb
import elastic_recheck.results as er_results

STEP = 3600000

LPCACHEDIR = os.path.expanduser('~/.launchpadlib/cache')

LOG = logging.getLogger('ergraph')


def get_launchpad_bug(bug):
    lp = launchpad.Launchpad.login_anonymously('grabbing bugs',
                                               'production',
                                               LPCACHEDIR)
    try:
        lp_bug = lp.bugs[bug]
        bugdata = {'name': lp_bug.title}
        projects = ", ".join(map(lambda x: "(%s - %s)" %
                                 (x.bug_target_name, x.status),
                                 lp_bug.bug_tasks))
        bugdata['affects'] = projects
        bugdata['reviews'] = get_open_reviews(bug)
    except KeyError:
        # if someone makes a bug private, we lose access to it.
        bugdata = dict(name='Unknown (Private Bug)',
                       affects='Unknown (Private Bug)', reviews=[])
    return bugdata


def get_open_reviews(bug_number):
    "return list of open gerrit reviews for a given bug."""
    r = requests.get("https://review.openstack.org:443/changes/"
                     "?q=status:open++message:`%s`+NOT+"
                     "project:openstack-infra/elastic-recheck" % bug_number)
    # strip off first few chars because 'the JSON response body starts with a
    # magic prefix line that must be stripped before feeding the rest of the
    # response body to a JSON parser'
    # https://review.openstack.org/Documentation/rest-api.html
    reviews = []
    result = None
    try:
        result = json.loads(r.text[4:])
    except ValueError:
        LOG.debug("gerrit response '%s' is not valid JSON" % r.text.strip())
        raise
    for review in result:
        reviews.append(review['_number'])
    return reviews


def main():
    parser = argparse.ArgumentParser(description='Generate data for graphs.')
    parser.add_argument(dest='queries',
                        help='path to query file')
    parser.add_argument('-o', dest='output',
                        help='output filename. Omit for stdout')
    parser.add_argument('-q', dest='queue',
                        help='limit results to a build queue regex')
    parser.add_argument('-c', '--conf', help="Elastic Recheck Configuration "
                        "file to use for data_source options such as "
                        "elastic search url, logstash url, and database "
                        "uri.")
    parser.add_argument('-v', dest='verbose',
                        action='store_true', default=False,
                        help='print out details as we go')
    args = parser.parse_args()

    # Start with defaults
    es_url = er.ES_URL
    ls_url = er.LS_URL
    db_uri = er.DB_URI

    if args.conf:
        config = ConfigParser.ConfigParser({'es_url': er.ES_URL,
                                            'ls_url': er.LS_URL,
                                            'db_uri': er.DB_URI})
        config.read(args.conf)
        if config.has_section('data_source'):
            es_url = config.get('data_source', 'es_url')
            ls_url = config.get('data_source', 'ls_url')
            db_uri = config.get('data_source', 'db_uri')

    classifier = er.Classifier(args.queries, es_url=es_url, db_uri=db_uri)

    buglist = []

    # if you don't hate timezones, you don't program enough
    epoch = datetime.utcfromtimestamp(0).replace(tzinfo=pytz.utc)
    ts = datetime.utcnow().replace(tzinfo=pytz.utc)
    # rawnow is useful for sending to javascript
    rawnow = int(((ts - epoch).total_seconds()) * 1000)

    ts = datetime(ts.year, ts.month, ts.day, ts.hour).replace(tzinfo=pytz.utc)
    # ms since epoch
    now = int(((ts - epoch).total_seconds()) * 1000)
    # number of days to match to, this should be the same as we are
    # indexing in logstash
    days = 10
    # How far back to start in the graphs
    start = now - (days * 24 * STEP)
    # ER timeframe for search
    timeframe = days * 24 * STEP / 1000

    last_indexed = int(
        ((classifier.most_recent() - epoch).total_seconds()) * 1000)
    behind = now - last_indexed

    # the data we're going to return, including interesting headers
    jsondata = {
        'now': rawnow,
        'last_indexed': last_indexed,
        'behind': behind,
        'buglist': []
    }

    for query in classifier.queries:
        if args.queue:
            query['query'] = query['query'] + (' AND build_queue:%s' %
                                               args.queue)
        if query.get('suppress-graph'):
            continue
        if args.verbose:
            LOG.debug("Starting query for bug %s" % query['bug'])
        logstash_query = qb.encode_logstash_query(query['query'],
                                                  timeframe=timeframe)
        logstash_url = ("%s/#/dashboard/file/logstash.json?%s"
                        % (ls_url, logstash_query))
        bug_data = get_launchpad_bug(query['bug'])
        bug = dict(number=query['bug'],
                   query=query['query'],
                   logstash_url=logstash_url,
                   bug_data=bug_data,
                   fails=0,
                   fails24=0,
                   data=[])
        buglist.append(bug)
        results = classifier.hits_by_query(query['query'],
                                           args.queue,
                                           size=3000)

        facets_for_fail = er_results.FacetSet()
        facets_for_fail.detect_facets(results,
                                      ["build_status", "build_uuid"])
        if "FAILURE" in facets_for_fail:
            bug['fails'] = len(facets_for_fail['FAILURE'])

        facets = er_results.FacetSet()
        facets.detect_facets(results,
                             ["build_status", "timestamp", "build_uuid"])

        for status in facets.keys():
            data = []
            for ts in range(start, now, STEP):
                if ts in facets[status]:
                    fails = len(facets[status][ts])
                    data.append([ts, fails])
                    # get the last 24 hr count as well, can't wait to have
                    # the pandas code and able to do it that way
                    if status == "FAILURE" and ts > (now - (24 * STEP)):
                        bug['fails24'] += fails
                else:
                    data.append([ts, 0])
            bug["data"].append(dict(label=status, data=data))

    # the sort order is a little odd, but basically sort by failures in
    # the last 24 hours, then with all failures for ones that we haven't
    # seen in the last 24 hours.
    buglist = sorted(buglist,
                     key=lambda bug: -(bug['fails24'] * 100000 + bug['fails']))

    jsondata['buglist'] = buglist
    if args.output:
        out = open(args.output, 'w')
    else:
        out = sys.stdout

    try:
        out.write(json.dumps(jsondata))
    finally:
        out.close()


if __name__ == "__main__":
    main()
