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
import operator
import os
import re

from launchpadlib import launchpad

import elastic_recheck.elasticRecheck as er
import elastic_recheck.results as er_results

LPCACHEDIR = os.path.expanduser('~/.launchpadlib/cache')


def get_options():
    parser = argparse.ArgumentParser(
        description='Query for existing recheck bugs.')
    parser.add_argument('--dir', '-d', help="Queries Directory",
                        default="queries")
    parser.add_argument('--lp', '-l', help="Query Launchpad",
                        type=bool,
                        default=False)
    parser.add_argument('--rate', '-r', help="Classification rate",
                        type=bool,
                        default=True)
    return parser.parse_args()


def all_fails(classifier):
    """Find all the the fails in the integrated gate.

    This attempts to find all the build jobs in the integrated gate
    so we can figure out how good we are doing on total classification.
    """
    all_fails = {}
    query = ('filename:"console.html" '
             'AND message:"Finished: FAILURE" '
             'AND build_queue:"gate"')
    results = classifier.hits_by_query(query, size=30000)
    facets = er_results.FacetSet()
    facets.detect_facets(results, ["build_uuid"])
    for build in facets:
        for result in facets[build]:
            # not perfect, but basically an attempt to show the integrated
            # gate. Would be nice if there was a zuul attr for this in es.
            if re.search("(^openstack/|devstack|grenade)", result.project):
                all_fails["%s.%s" % (build, result.build_name)] = False
    return all_fails


def classifying_rate(classifier, data):
    """Builds and prints the classification rate.

    It's important to know how good a job we are doing, so this
    tool runs through all the failures we've got and builds the
    classification rate. For every failure in the gate queue did
    we find a match for it.
    """
    fails = all_fails(classifier)
    for bugnum in data:
        bug = data[bugnum]
        for job in bug['failed_jobs']:
            fails[job] = True

    total = len(fails.keys())
    bad_jobs = {}
    count = 0
    for f in fails:
        if fails[f] is True:
            count += 1
        else:
            build, job = f.split('.', 1)
            if job in bad_jobs:
                bad_jobs[job] += 1
            else:
                bad_jobs[job] = 1

    print("Classification percentage: %2.2f%%" %
          ((float(count) / float(total)) * 100.0))
    sort = sorted(
        bad_jobs.iteritems(),
        key=operator.itemgetter(1),
        reverse=True)
    print("Job fails with most unclassified errors")
    for s in sort:
        print "  %3s : %s" % (s[1], s[0])


def collect_metrics(classifier):
    data = {}
    for q in classifier.queries:
        results = classifier.hits_by_query(q['query'], size=30000)
        facets = er_results.FacetSet()
        facets.detect_facets(
            results,
            ["build_status", "build_uuid"])

        num_fails = 0
        failed_jobs = []
        if "FAILURE" in facets:
            num_fails = len(facets["FAILURE"])
            for build in facets["FAILURE"]:
                for result in facets["FAILURE"][build]:
                    failed_jobs.append("%s.%s" % (build, result.build_name))

        data[q['bug']] = {
            'fails': num_fails,
            'hits': facets,
            'query': q['query'],
            'failed_jobs': failed_jobs
        }

    return data


def print_metrics(data, with_lp=False):
    print "Elastic recheck known issues"
    print

    sorted_data = sorted(data.iteritems(),
                         key=lambda x: -x[1]['fails'])
    for d in sorted_data:
        print("Bug: https://bugs.launchpad.net/bugs/%s => %s"
              % (d[0], d[1]['query'].rstrip()))
        if with_lp:
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
    print_metrics(data, with_lp=opts.lp)
    if opts.rate:
        classifying_rate(classifier, data)


if __name__ == "__main__":
    main()
