#!/usr/bin/env python

# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import argparse
import os

from launchpadlib import launchpad

import elastic_recheck.elasticRecheck as er
import elastic_recheck.results as er_results

LPCACHEDIR = os.path.expanduser('~/.launchpadlib/cache')


def get_options():
    parser = argparse.ArgumentParser(
        description='Query for existing recheck bugs.')
    parser.add_argument('--dir', '-d', help="Queries Directory",
                        default="queries")
    return parser.parse_args()


def collect_metrics(classifier):
    data = {}
    for q in classifier.queries:
        results = classifier.hits_by_query(q['query'], size=30000)
        facets = er_results.FacetSet()
        facets.detect_facets(results, ["build_status", "build_uuid"])

        num_fails = 0
        if "FAILURE" in facets:
            num_fails = len(facets["FAILURE"])

        data[q['bug']] = {
            'fails': num_fails,
            'hits': facets,
            'query': q['query']
            }

    return data


def print_metrics(data):
    print "Elastic recheck known issues"
    print

    sorted_data = sorted(data.iteritems(),
                         key=lambda x: -x[1]['fails'])
    for d in sorted_data:
        print("Bug: https://bugs.launchpad.net/bugs/%s => %s"
              % (d[0], d[1]['query'].rstrip()))
        get_launchpad_bug(d[0])
        print "Hits"
        for s in d[1]['hits'].keys():
            print "  %s: %s" % (s, len(d[1]['hits'][s]))
        print


def get_launchpad_bug(bug):
    lp = launchpad.Launchpad.login_anonymously('grabbing bugs',
                                               'production',
                                               LPCACHEDIR)
    lp_bug = lp.bugs[bug]
    print "Title: %s" % lp_bug.title
    targets = map(lambda x: (x.bug_target_name, x.status), lp_bug.bug_tasks)
    print "Project: Status"
    for target, status in targets:
        print "  %s: %s" % (target, status)


def main():
    opts = get_options()
    classifier = er.Classifier(opts.dir)
    data = collect_metrics(classifier)
    print_metrics(data)


if __name__ == "__main__":
    main()
