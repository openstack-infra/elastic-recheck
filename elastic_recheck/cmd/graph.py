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
import base64
from datetime import datetime
import json
import os

from launchpadlib import launchpad

import elastic_recheck.elasticRecheck as er
from elastic_recheck import results as er_results

STEP = 3600000

LPCACHEDIR = os.path.expanduser('~/.launchpadlib/cache')


def get_launchpad_bug(bug):
    lp = launchpad.Launchpad.login_anonymously('grabbing bugs',
                                               'production',
                                               LPCACHEDIR)
    lp_bug = lp.bugs[bug]
    bugdata = {'name': lp_bug.title}
    projects = ", ".join(map(lambda x: "(%s - %s)" %
                             (x.bug_target_name, x.status),
                             lp_bug.bug_tasks))
    bugdata['affects'] = projects
    return bugdata


def main():
    parser = argparse.ArgumentParser(description='Generate data for graphs.')
    parser.add_argument(dest='queries',
                        help='path to query file')
    parser.add_argument('-o', dest='output',
                        help='output filename')
    args = parser.parse_args()

    classifier = er.Classifier(args.queries)

    buglist = []

    epoch = datetime.utcfromtimestamp(0)
    ts = datetime.now()
    ts = datetime(ts.year, ts.month, ts.day, ts.hour)
    # ms since epoch
    now = int(((ts - epoch).total_seconds()) * 1000)
    start = now - (14 * 24 * STEP)

    for query in classifier.queries:
        urlq = dict(search=query['query'],
                    fields=[],
                    offset=0,
                    timeframe="604800",
                    graphmode="count")
        logstash_query = base64.urlsafe_b64encode(json.dumps(urlq))
        bug_data = get_launchpad_bug(query['bug'])
        bug = dict(number=query['bug'],
                   query=query['query'],
                   logstash_query=logstash_query,
                   bug_data=bug_data,
                   fails=0,
                   data=[])
        buglist.append(bug)
        results = classifier.hits_by_query(query['query'], size=3000)

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
                    data.append([ts, len(facets[status][ts])])
                else:
                    data.append([ts, 0])
            bug["data"].append(dict(label=status, data=data))

    buglist = sorted(buglist, key=lambda bug: -bug['fails'])

    out = open(args.output, 'w')
    out.write(json.dumps(buglist))
    out.close()


if __name__ == "__main__":
    main()
