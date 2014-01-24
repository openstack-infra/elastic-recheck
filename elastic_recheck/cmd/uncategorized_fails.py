#!/usr/bin/env python

# Copyright 2014 Samsung Electronics. All Rights Reserved.
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
import operator
import re
import time

import jinja2

import elastic_recheck.elasticRecheck as er
import elastic_recheck.results as er_results


def get_options():
    parser = argparse.ArgumentParser(
        description='''Build the list of all uncategorized test runs.

        Note: This will take a few minutes to run.''')
    parser.add_argument('--dir', '-d', help="Queries Directory",
                        default="queries")
    parser.add_argument('-t', '--templatedir', help="Template Directory")
    parser.add_argument('-o', '--output', help="Output File")
    return parser.parse_args()


def setup_template_engine(directory):
    path = ["web/share/templates"]
    if directory:
        path.append(directory)

    loader = jinja2.FileSystemLoader(path)
    env = jinja2.Environment(loader=loader)
    return env.get_template("uncategorized.html")


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
                name = result.build_name
                timestamp = time.strptime(result.timestamp,
                                          "%Y-%m-%dT%H:%M:%S.%fZ")
                log = result.log_url.split("console.html")[0]
                all_fails["%s.%s" % (build, name)] = {
                    'log': log,
                    'timestamp': timestamp
                   }
    return all_fails


def num_fails_per_build_name(all_jobs):
    counts = collections.defaultdict(int)
    for f in all_jobs:
        build, job = f.split('.', 1)
        counts[job] += 1
    return counts


def classifying_rate(fails, data, engine):
    """Builds and prints the classification rate.

    It's important to know how good a job we are doing, so this
    tool runs through all the failures we've got and builds the
    classification rate. For every failure in the gate queue did
    we find a match for it.
    """
    found_fails = {k: False for (k, v) in fails.iteritems()}

    for bugnum in data:
        bug = data[bugnum]
        for job in bug['failed_jobs']:
            found_fails[job] = True

    total = len(found_fails.keys())
    bad_jobs = collections.defaultdict(int)
    total_job_failures = collections.defaultdict(int)
    bad_job_urls = collections.defaultdict(list)
    count = 0
    for f in fails:
        build, job = f.split('.', 1)
        total_job_failures[job] += 1
        if found_fails[f] is True:
            count += 1
        else:
            bad_jobs[job] += 1
            bad_job_urls[job].append(fails[f])

    for job in bad_job_urls:
        # sort by timestamp.
        bad_job_urls[job] = sorted(bad_job_urls[job],
                                   key=lambda v: v['timestamp'], reverse=True)
        # Convert timestamp into string
        for url in bad_job_urls[job]:
            url['timestamp'] = time.strftime(
                "%Y-%m-%dT%H:%M",
                url['timestamp'])

    classifying_rate = collections.defaultdict(int)
    classifying_rate['overall'] = "%.1f" % (
        (float(count) / float(total)) * 100.0)
    for job in bad_jobs:
        if bad_jobs[job] == 0 and total_job_failures[job] == 0:
            classifying_rate[job] = 0
        else:
            classifying_rate[job] = "%.1f" % (
                100.0 -
                (float(bad_jobs[job]) / float(total_job_failures[job]))
                * 100.0)
    sort = sorted(
        bad_jobs.iteritems(),
        key=operator.itemgetter(1),
        reverse=True)

    tvars = {
        "rate": classifying_rate,
        "jobs": sort,
        "total_job_failures": total_job_failures,
        "urls": bad_job_urls
    }
    return engine.render(tvars)


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
        results = classifier.hits_by_query(q['query'], size=30000)
        hits = _status_count(results)
        data[q['bug']] = {
            'fails': _failure_count(hits),
            'hits': hits,
            'percentages': _failure_percentage(results, fails),
            'query': q['query'],
            'failed_jobs': _failed_jobs(results)
        }

    return data


def main():
    opts = get_options()
    classifier = er.Classifier(opts.dir)
    fails = all_fails(classifier)
    data = collect_metrics(classifier, fails)
    engine = setup_template_engine(opts.templatedir)
    html = classifying_rate(fails, data, engine)
    if opts.output:
        with open(opts.output, "w") as f:
            f.write(html)
    else:
        print html


if __name__ == "__main__":
    main()
