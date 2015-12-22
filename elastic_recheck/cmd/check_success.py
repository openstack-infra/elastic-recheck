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
import collections
import logging
import operator
import os
import re
import time

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
    """Find all the fails in the integrated gate.

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


def num_fails_per_build_name(all_jobs):
    counts = collections.defaultdict(int)
    for f in all_jobs:
        build, job = f.split('.', 1)
        counts[job] += 1
    return counts


def classifying_rate(fails, data):
    """Builds and prints the classification rate.

    It's important to know how good a job we are doing, so this
    tool runs through all the failures we've got and builds the
    classification rate. For every failure in the gate queue did
    we find a match for it.
    """
    for bugnum in data:
        bug = data[bugnum]
        for job in bug['failed_jobs']:
            fails[job] = True

    total = len(fails.keys())
    bad_jobs = collections.defaultdict(int)
    count = 0
    for f in fails:
        if fails[f] is True:
            count += 1
        else:
            build, job = f.split('.', 1)
            bad_jobs[job] += 1

    print("Classification percentage: %2.2f%%" %
          ((float(count) / float(total)) * 100.0))
    sort = sorted(
        bad_jobs.iteritems(),
        key=operator.itemgetter(1),
        reverse=True)
    print("Job fails with most unclassified errors")
    for s in sort:
        print "  %3s : %s" % (s[1], s[0])


def _status_count(results):
    counts = {}
    facets = er_results.FacetSet()
    facets.detect_facets(
        results,
        ["build_status", "build_uuid"])

    for key in facets:
        counts[key] = len(facets[key])
    return counts


def _failure_count(hits):
    if "FAILURE" in hits:
        return hits["FAILURE"]
    else:
        return 0


def _failed_jobs(results):
    failed_jobs = []
    facets = er_results.FacetSet()
    facets.detect_facets(
        results,
        ["build_status", "build_uuid"])
    if "FAILURE" in facets:
        for build in facets["FAILURE"]:
            for result in facets["FAILURE"][build]:
                failed_jobs.append("%s.%s" % (build, result.build_name))
    return failed_jobs


def _count_fails_per_build_name(hits):
    facets = er_results.FacetSet()
    counts = collections.defaultdict(int)
    facets.detect_facets(
        hits,
        ["build_status", "build_name", "build_uuid"])
    if "FAILURE" in facets:
        for build_name in facets["FAILURE"]:
            counts[build_name] += 1
    return counts


def _failure_percentage(hits, fails):
    total_fails_per_build_name = num_fails_per_build_name(fails)
    fails_per_build_name = _count_fails_per_build_name(hits)
    per = {}
    for build in fails_per_build_name:
        this_job = fails_per_build_name[build]
        if build in total_fails_per_build_name:
            total = total_fails_per_build_name[build]
            per[build] = (float(this_job) / float(total)) * 100.0
    return per


def collect_metrics(classifier, fails):
    data = {}
    for q in classifier.queries:
        start = time.time()
        results = classifier.hits_by_query(q['query'], size=30000)
        log = logging.getLogger('recheckwatchbot')
        log.debug("Took %d seconds to run (uncached) query for bug %s" %
                  (time.time() - start, q['bug']))
        hits = _status_count(results)
        data[q['bug']] = {
            'fails': _failure_count(hits),
            'hits': hits,
            'percentages': _failure_percentage(results, fails),
            'query': q['query'],
            'failed_jobs': _failed_jobs(results)
        }

    return data


def print_metrics(data, with_lp=False):
    print "Elastic recheck known issues"
    print

    sorted_data = sorted(data.iteritems(),
                         key=lambda x: -x[1]['fails'])
    for d in sorted_data:
        bug = d[0]
        data = d[1]
        print("Bug: https://bugs.launchpad.net/bugs/%s => %s"
              % (bug, data['query'].rstrip()))
        if with_lp:
            get_launchpad_bug(d[0])
        print "Hits"
        for s in data['hits']:
            print "  %s: %s" % (s, data['hits'][s])
        print "Percentage of Gate Queue Job failures triggered by this bug"
        for s in data['percentages']:
            print "  %s: %2.2f%%" % (s, data['percentages'][s])
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
    fails = all_fails(classifier)
    data = collect_metrics(classifier, fails)
    print_metrics(data, with_lp=opts.lp)
    if opts.rate:
        classifying_rate(fails, data)


if __name__ == "__main__":
    main()
