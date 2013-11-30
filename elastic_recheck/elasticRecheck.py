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
import urllib2

import ConfigParser
import logging
import os
import sys
import time

import elastic_recheck.loader as loader
import elastic_recheck.query_builder as qb
from elastic_recheck import results

logging.basicConfig()


REQUIRED_FILES = [
        'console.html',
        'logs/screen-n-api.txt',
        'logs/screen-n-cpu.txt',
        'logs/screen-n-sch.txt',
        'logs/screen-c-api.txt',
        'logs/screen-c-vol.txt',
        'logs/syslog.txt',
        ]


class Stream(object):
    """Gerrit Stream.

    Monitors gerrit stream looking for tempest-devstack failures.
    """

    log = logging.getLogger("recheckwatchbot")

    def __init__(self, user, host, key, thread=True):
        port = 29418
        self.gerrit = gerritlib.gerrit.Gerrit(host, user, port, key)
        if thread:
            self.gerrit.startWatching()

    def get_failed_tempest(self):
        self.log.debug("entering get_failed_tempest")
        while True:
            event = self.gerrit.getEvent()
            if event.get('type', '') != 'comment-added':
                continue
            username = event['author'].get('username', '')
            if (username == 'jenkins' and
                    "Build failed.  For information on how to proceed" in
                    event['comment']):
                self.log.debug("potential failed_tempest")
                found = False
                for line in event['comment'].split('\n'):
                    if "FAILURE" in line and ("python2" in line or "pep8" in line):
                        # Unit Test Failure
                        found = False
                        break
                    if "FAILURE" in line and "tempest-devstack" in line:
                        url = [x for x in line.split() if "http" in x][0]
                        if RequiredFiles.files_at_url(url):
                            self.log.debug("All file present")
                            found = True
                if found:
                    return event
                continue

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
    log = logging.getLogger("recheckwatchbot")
    ES_URL = "http://logstash.openstack.org/elasticsearch"

    queries = None

    def __init__(self, queries_dir):
        self.es = results.SearchEngine(self.ES_URL)
        self.queries_dir = queries_dir
        self.queries = loader.load(self.queries_dir)

    def hits_by_query(self, query, facet=None, size=100):
        es_query = qb.generic(query, facet=facet)
        return self.es.search(es_query, size=size)

    def classify(self, change_number, patch_number, comment):
        """Returns either empty list or list with matched bugs."""
        self.log.debug("Entering classify")
        #Reload each time
        self.queries = loader.load(self.queries_dir)
        #Wait till Elastic search is ready
        self.log.debug("checking if ElasticSearch is ready")
        if not self._is_ready(change_number, patch_number, comment):
            self.log.error("something went wrong, ElasticSearch is still not ready, "
                    "giving up and trying next failure")
            return None
        self.log.debug("ElasticSearch is ready, starting to classify")
        bug_matches = []
        for x in self.queries:
            self.log.debug("Looking for bug: https://bugs.launchpad.net/bugs/%s" % x['bug'])
            query = qb.single_patch(x['query'], change_number, patch_number)
            results = self.es.search(query, size='10')
            if self._urls_match(comment, results):
                bug_matches.append(x['bug'])
        return bug_matches

    def _is_ready(self, change_number, patch_number, comment):
        """Wait till ElasticSearch is ready, but return False if timeout."""
        NUMBER_OF_RETRIES = 20
        SLEEP_TIME = 40
        query = qb.result_ready(change_number, patch_number)
        for i in range(NUMBER_OF_RETRIES):
            try:
                results = self.es.search(query, size='10')
            except pyelasticsearch.exceptions.InvalidJsonResponseError:
                # If ElasticSearch returns an error code, sleep and retry
                #TODO(jogo): if this works pull out search into a helper function that  does this.
                print "UHUH hit InvalidJsonResponseError"
                time.sleep(NUMBER_OF_RETRIES)
                continue
            if (len(results) > 0 and self._urls_match(comment, results)):
                break
            else:
                time.sleep(SLEEP_TIME)
        if i == NUMBER_OF_RETRIES - 1:
            return False
        self.log.debug("Found hits for change_number: %s, patch_number: %s" % (change_number, patch_number))
        query = qb.files_ready(change_number, patch_number)
        for i in range(NUMBER_OF_RETRIES):
            results = self.es.search(query, size='80')
            files = [x['term'] for x in results.terms]
            missing_files = [x for x in REQUIRED_FILES if x not in files]
            if len(missing_files) is 0:
                break
            else:
                time.sleep(SLEEP_TIME)
        if i == NUMBER_OF_RETRIES - 1:
            return False
        self.log.debug("All files present for change_number: %s, patch_number: %s" % (change_number, patch_number))
        # Just because one file is parsed doesn't mean all are, so wait a
        # bit
        time.sleep(10)
        return True

    def _urls_match(self, comment, results):
        for result in results:
            url = result.log_url
            if RequiredFiles.prep_url(url) in comment:
                return True
        return False


class RequiredFiles(object):

    log = logging.getLogger("recheckwatchbot")

    @staticmethod
    def prep_url(url):
        if isinstance(url, list):
            # The url is sometimes a list of one value
            url = url[0]
        if "/logs/" in url:
            return '/'.join(url.split('/')[:-2])
        return '/'.join(url.split('/')[:-1])

    @staticmethod
    def files_at_url(url):
        for f in REQUIRED_FILES:
            try:
                urllib2.urlopen(url + '/' + f)
            except urllib2.HTTPError:
                try:
                    urllib2.urlopen(url + '/' + f + '.gz')
                except urllib2.HTTPError:
                    # File does not exist at URL
                    RequiredFiles.log.debug("missing file %s" % f)
                    return False
        return True


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
        bug_numbers = classifier.classify(change, rev, event['comment'])
        if not bug_numbers:
            print "unable to classify failure"
        else:
            for bug_number in bug_numbers:
                print "Found bug: https://bugs.launchpad.net/bugs/%s" % bug_number

if __name__ == "__main__":
    main()
