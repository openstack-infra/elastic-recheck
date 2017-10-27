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
import datetime
import logging
import operator
import os
import re
import requests

import dateutil.parser as dp
import jinja2

import elastic_recheck.config as er_config
import elastic_recheck.elasticRecheck as er
import elastic_recheck.query_builder as qb
import elastic_recheck.results as er_results

LOG = logging.getLogger('eruncategorized')


def get_options():
    parser = argparse.ArgumentParser(
        description='''Build the list of all uncategorized test runs.

        Note: This will take a few minutes to run.''')
    parser.add_argument('--dir', '-d', help="Queries Directory",
                        default="queries")
    parser.add_argument('-t', '--templatedir', help="Template Directory")
    parser.add_argument('-o', '--output',
                        help="The path for the directory to store the "
                             "html output. 2 files will be created: "
                             "integrated_gate.html and others.html. "
                             "If this option is not specified these files "
                             "will be written to the cwd.")
    parser.add_argument('-c', '--conf', help="Elastic Recheck Configuration "
                        "file to use for data_source options such as "
                        "elastic search url, logstash url, and database "
                        "uri.")
    parser.add_argument('--search-size',
                        help="Max search results elastic search should return",
                        default=er_config.UNCAT_MAX_SEARCH_SIZE)

    parser.add_argument('--all-fails-query',
                        help="Query to find all failures in elastic search",
                        default=er_config.ALL_FAILS_QUERY)

    parser.add_argument('--excluded-jobs-regex',
                        help="Regular express to exclude jobs from results",
                        default=er_config.EXCLUDED_JOBS_REGEX)

    parser.add_argument('--included-projects-regex',
                        help="Regular express to include only certain projects"
                             " in results",
                        default=er_config.INCLUDED_PROJECTS_REGEX)
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Print status as we go")
    return parser.parse_args()


def setup_template_engine(directory, group='integrated_gate'):
    path = ["web/share/templates"]
    if directory:
        path.append(directory)

    loader = jinja2.FileSystemLoader(path)
    env = jinja2.Environment(loader=loader)
    if group == 'integrated_gate':
        filename = 'integrated_gate.html'
    elif group == 'others':
        filename = 'others.html'
    else:
        raise TypeError('Unknown job name %s' % group)
    return env.get_template(filename)


def all_fails(classifier, config=None):
    """Find all the the fails in the integrated gate.

    This attempts to find all the build jobs in the integrated gate
    so we can figure out how good we are doing on total classification.
    """

    config = config or er_config.Config()
    integrated_fails = {}
    other_fails = {}
    all_fails = {}
    results = classifier.hits_by_query(config.all_fails_query,
                                       size=config.uncat_search_size)
    facets = er_results.FacetSet()
    facets.detect_facets(results, ["build_uuid"])
    for build in facets:
        for result in facets[build]:
            # If the job is on the exclude list, skip
            if re.search(config.excluded_jobs_regex, result.build_name):
                continue

            integrated_gate_projects = [
                'openstack/cinder',
                'openstack/glance',
                'openstack/keystone',
                'openstack/neutron',
                'openstack/nova',
                'openstack/requirements',
                'openstack/tempest',
                'openstack-dev/devstack',
                'openstack-dev/grenade',
                'openstack-infra/devstack-gate',
            ]
            if result.project in integrated_gate_projects:
                name = result.build_name
                timestamp = dp.parse(result.timestamp)
                if 'console.html' in result.log_url:
                    log = result.log_url.split('console.html')[0]
                elif 'job-output.txt' in result.log_url:
                    log = result.log_url.split('job-output.txt')[0]
                integrated_fails["%s.%s" % (build, name)] = {
                    'log': log,
                    'timestamp': timestamp,
                    'build_uuid': result.build_uuid
                }
            else:
                # not perfect, but basically an attempt to show the integrated
                # gate. Would be nice if there was a zuul attr for this in es.
                if re.search(config.included_projects_regex, result.project):
                    name = result.build_name
                    timestamp = dp.parse(result.timestamp)
                    if 'console.html' in result.log_url:
                        log = result.log_url.split('console.html')[0]
                    elif 'job-output.txt' in result.log_url:
                        log = result.log_url.split('job-output.txt')[0]
                    other_fails["%s.%s" % (build, name)] = {
                        'log': log,
                        'timestamp': timestamp,
                        'build_uuid': result.build_uuid
                    }

            LOG.debug("Found failure: %s build_uuid: %s project %s",
                      len(all_fails), result.build_uuid, result.project)

    all_fails = {
        'integrated_gate': integrated_fails,
        'others': other_fails
    }
    return all_fails


def num_fails_per_build_name(all_jobs):
    counts = collections.defaultdict(int)
    for f in all_jobs:
        build, job = f.split('.', 1)
        counts[job] += 1
    return counts


def classifying_rate(fails, data, engine, classifier, ls_url):
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

    bad_jobs = collections.defaultdict(int)
    total_job_failures = collections.defaultdict(int)
    bad_job_urls = collections.defaultdict(list)
    count = 0
    total = 0
    for f in fails:
        total += 1
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
            url['timestamp'] = url['timestamp'].strftime(
                "%Y-%m-%dT%H:%M")
            # setup crm114 query for build_uuid
            query = ('build_uuid: "%s" '
                     'AND error_pr:["-1000.0" TO "-10.0"] '
                     % url['build_uuid'])
            logstash_query = qb.encode_logstash_query(query)
            logstash_url = ('%s/#/dashboard/file/logstash.json?%s'
                            % (ls_url, logstash_query))
            LOG.debug("looking up hits for job %s query %s", job, query)
            results = classifier.hits_by_query(query, size=1)
            if results:
                url['crm114'] = logstash_url
                LOG.debug("Hits found. Using logstash url %s",
                          logstash_url)

    classifying_rate = collections.defaultdict(int)
    rate = 0
    # avoid a divide by 0
    if total > 0:
        rate = (float(count) / float(total)) * 100.0

    classifying_rate['overall'] = "%.1f" % rate
    LOG.debug("overall classifying_rate is %s", classifying_rate['overall'])
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
        "count": count,
        "total": total,
        "uncounted": total - count,
        "jobs": sort,
        "total_job_failures": total_job_failures,
        "urls": bad_job_urls,
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M")
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


def collect_metrics(classifier, fails, config=None):
    config = config or er_config.Config()
    data = {}
    for q in classifier.queries:
        try:
            results = classifier.hits_by_query(q['query'],
                                               size=config.uncat_search_size)
            hits = _status_count(results)
            LOG.debug("Collected metrics for query %s, hits %s", q['query'],
                      hits)
            data[q['bug']] = {
                'fails': _failure_count(hits),
                'hits': hits,
                'percentages': _failure_percentage(results, fails),
                'query': q['query'],
                'failed_jobs': _failed_jobs(results)
            }
        except requests.exceptions.ReadTimeout:
            LOG.exception("Failed to collection metrics for query %s" %
                          q['query'])
    return data


def main():
    opts = get_options()
    config = er_config.Config(
        config_file=opts.conf,
        uncat_search_size=opts.search_size,
        all_fails_query=opts.all_fails_query,
        excluded_jobs_regex=opts.excluded_jobs_regex,
        included_projects_regex=opts.included_projects_regex)

    classifier = er.Classifier(opts.dir, config=config)
    all_gate_fails = all_fails(classifier, config=config)
    if opts.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(format='%(asctime)s [%(name)s]  %(levelname)s: '
                               '%(message)s', level=level)
    if level == logging.INFO:
        # NOTE(mtreinish: This logger is overly chatty at INFO logging every
        # time an HTTP connection is established. This isn't really useful
        # at INFO for this command
        logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(
            logging.WARN)

    LOG.info("Starting search for unclassified failures")
    for group in all_gate_fails:
        LOG.info("Processing failures for group: %s", group)
        fails = all_gate_fails[group]
        if not fails:
            continue
        data = collect_metrics(classifier, fails, config=config)
        engine = setup_template_engine(opts.templatedir, group=group)
        html = classifying_rate(fails, data, engine, classifier, config.ls_url)
        if opts.output:
            out_dir = opts.output
        else:
            out_dir = os.getcwd()
        with open(os.path.join(out_dir, group + '.html'), "w") as f:
            f.write(html)


if __name__ == "__main__":
    main()
