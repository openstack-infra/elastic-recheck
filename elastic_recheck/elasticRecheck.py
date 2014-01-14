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


import gerritlib.gerrit
import pyelasticsearch

import ConfigParser
import datetime
import logging
import os
import re
import sys
import time

import elastic_recheck.loader as loader
import elastic_recheck.query_builder as qb
from elastic_recheck import results

LOG = logging.getLogger("recheckwatchbot")

ES_URL = "http://logstash.openstack.org/elasticsearch"


def required_files(job):
    files = ['console.html']
    if re.match("tempest-dsvm", job):
        files.extend([
            'logs/screen-n-api.txt',
            'logs/screen-n-cpu.txt',
            'logs/screen-n-sch.txt',
            'logs/screen-c-api.txt',
            'logs/screen-c-vol.txt',
            'logs/syslog.txt'])
    return files


class ResultNotReady(Exception):
    pass


class Stream(object):
    """Gerrit Stream.

    Monitors gerrit stream looking for tempest-devstack failures.
    """
    def __init__(self, user, host, key, thread=True):
        port = 29418
        self.gerrit = gerritlib.gerrit.Gerrit(host, user, port, key)
        self.es = results.SearchEngine(ES_URL)
        if thread:
            self.gerrit.startWatching()

    @staticmethod
    def parse_jenkins_failure(event):
        """Is this comment a jenkins failure comment."""
        if event.get('type', '') != 'comment-added':
            LOG.debug("Skipping event type %s" % event.get('type', ''))
            return False

        username = event['author'].get('username', '')
        if (username != 'jenkins'):
            LOG.debug("Skipping comment from %s" %
                      event['author'].get('username', ''))
            return False

        if not ("Build failed.  For information on how to proceed" in
                event['comment']):
            change = event['change']['number']
            rev = event['patchSet']['number']
            LOG.debug("Skipping passing job %s,%s" % (change, rev))
            return False

        failed_tests = {}
        for line in event['comment'].split("\n"):
            m = re.search("- ([\w-]+)\s*(http://\S+)\s*:\s*FAILURE", line)
            if m:
                failed_tests[m.group(1)] = m.group(2)
        return failed_tests

    def _job_console_uploaded(self, change, patch, name):
        query = qb.result_ready(change, patch, name)
        r = self.es.search(query, size='10')
        if len(r) == 0:
            raise ResultNotReady()
        else:
            LOG.debug("Console ready for %s %s,%s" %
                      (name, change, patch))

    def _has_required_files(self, change, patch, name):
        query = qb.files_ready(change, patch)
        r = self.es.search(query, size='80')
        files = [x['term'] for x in r.terms]
        required = required_files(name)
        missing_files = [x for x in required if x not in files]
        if len(missing_files) != 0:
            raise ResultNotReady()

    def _is_openstack_project(self, event):
        return "tempest-dsvm-full" in event["comment"]

    def _does_es_have_data(self, change_number, patch_number, job_fails):
        """Wait till ElasticSearch is ready, but return False if timeout."""
        NUMBER_OF_RETRIES = 20
        SLEEP_TIME = 40
        started_at = datetime.datetime.now()
        # this checks that we've got the console log uploaded, need to retry
        # in case ES goes bonkers on cold data, which it does some times.
        for i in range(NUMBER_OF_RETRIES):
            try:
                for job_name in job_fails:
                    self._job_console_uploaded(
                        change_number, patch_number, job_name)
                break

            except ResultNotReady:
                LOG.debug("Console logs not ready for %s %s,%s" %
                          (job_name, change_number, patch_number))
                time.sleep(SLEEP_TIME)
                continue
            except pyelasticsearch.exceptions.InvalidJsonResponseError:
                # If ElasticSearch returns an error code, sleep and retry
                # TODO(jogo): if this works pull out search into a helper
                # function that  does this.
                LOG.exception(
                    "Elastic Search not responding on attempt %d" % i)
                time.sleep(NUMBER_OF_RETRIES)
                continue

        if i == NUMBER_OF_RETRIES - 1:
            elapsed = datetime.datetime.now() - started_at
            LOG.warn("Console logs not available after %ss for %s %s,%s" %
                     (elapsed, job_name, change_number, patch_number))
            return False

        LOG.debug(
            "Found hits for change_number: %s, patch_number: %s"
            % (change_number, patch_number))

        for i in range(NUMBER_OF_RETRIES):
            try:
                for job_name in job_fails:
                    self._has_required_files(
                        change_number, patch_number, job_name)
                LOG.info(
                    "All files present for change_number: %s, patch_number: %s"
                    % (change_number, patch_number))
                time.sleep(10)
                return True
            except ResultNotReady:
                time.sleep(SLEEP_TIME)

        # if we get to the end, we're broken
        elapsed = datetime.datetime.now() - started_at
        LOG.warn("Required files not ready after %ss for %s %d,%d" %
                 (elapsed, job_name, change_number, patch_number))
        return False

    def get_failed_tempest(self):
        LOG.debug("entering get_failed_tempest")
        while True:
            event = self.gerrit.getEvent()

            failed_jobs = Stream.parse_jenkins_failure(event)
            if not failed_jobs:
                # nothing to see here, lets try the next event
                continue

            # bail if it's not an openstack project
            if not self._is_openstack_project(event):
                continue

            change = event['change']['number']
            rev = event['patchSet']['number']
            LOG.info("Looking for failures in %s,%s on %s" %
                     (change, rev, ", ".join(failed_jobs)))
            if self._does_es_have_data(change, rev, failed_jobs):
                return event

    def leave_comment(self, project, commit, bugs=None):
        if bugs:
            bug_urls = ['https://bugs.launchpad.net/bugs/%s' % x for x in bugs]
            message = """I noticed tempest failed, I think you hit bug(s):

- %(bugs)s

We don't automatically recheck or reverify, so please consider
doing that manually if someone hasn't already. For a code review
which is not yet approved, you can recheck by leaving a code
review comment with just the text:

    recheck bug %(bug)s

For a code review which has been approved but failed to merge,
you can reverify by leaving a comment like this:

    reverify bug %(bug)s""" % {'bugs': "\n- ".join(bug_urls),
                               'bug': bugs[0]}
        else:
            message = ("I noticed tempest failed, refer to: "
                       "https://wiki.openstack.org/wiki/"
                       "GerritJenkinsGithub#Test_Failures")
        self.gerrit.review(project, commit, message)


class Classifier():
    """Classify failed tempest-devstack jobs based.

    Given a change and revision, query logstash with a list of known queries
    that are mapped to specific bugs.
    """
    queries = None

    def __init__(self, queries_dir):
        self.es = results.SearchEngine(ES_URL)
        self.queries_dir = queries_dir
        self.queries = loader.load(self.queries_dir)

    def hits_by_query(self, query, facet=None, size=100):
        es_query = qb.generic(query, facet=facet)
        return self.es.search(es_query, size=size)

    def classify(self, change_number, patch_number, skip_resolved=True):
        """Returns either empty list or list with matched bugs."""
        LOG.debug("Entering classify")
        #Reload each time
        self.queries = loader.load(self.queries_dir, skip_resolved)
        bug_matches = []
        for x in self.queries:
            LOG.debug(
                "Looking for bug: https://bugs.launchpad.net/bugs/%s"
                % x['bug'])
            query = qb.single_patch(x['query'], change_number, patch_number)
            results = self.es.search(query, size='10')
            if len(results) > 0:
                bug_matches.append(x['bug'])
        return bug_matches


def main():
    config = ConfigParser.ConfigParser()
    if len(sys.argv) is 2:
        config_path = sys.argv[1]
    else:
        config_path = 'elasticRecheck.conf'
    config.read(config_path)
    user = config.get('gerrit', 'user', 'jogo')
    host = config.get('gerrit', 'host', 'review.openstack.org')
    queries = config.get('gerrit', 'query_file', 'queries.yaml')
    queries = os.path.expanduser(queries)
    key = config.get('gerrit', 'key')
    classifier = Classifier(queries)
    stream = Stream(user, host, key)
    while True:
        event = stream.get_failed_tempest()
        change = event['change']['number']
        rev = event['patchSet']['number']
        print "======================="
        print "https://review.openstack.org/#/c/%(change)s/%(rev)s" % locals()
        bug_numbers = classifier.classify(change, rev)
        if not bug_numbers:
            print "unable to classify failure"
        else:
            for bug_number in bug_numbers:
                print("Found bug: https://bugs.launchpad.net/bugs/%s"
                      % bug_number)

if __name__ == "__main__":
    main()
