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

import datetime
import logging
import re
import time

import elastic_recheck.loader as loader
import elastic_recheck.query_builder as qb
from elastic_recheck import results

ES_URL = "http://logstash.openstack.org/elasticsearch"


def required_files(job):
    files = ['console.html']
    if re.match("tempest-dsvm", job):
        files.extend([
            'logs/screen-n-api.txt',
            'logs/screen-n-cpu.txt',
            'logs/screen-n-sch.txt',
            'logs/screen-g-api.txt',
            'logs/screen-c-api.txt',
            'logs/screen-c-vol.txt',
            'logs/syslog.txt'])
        # we could probably add more neutron files
        # but currently only q-svc is used in queries
        if re.match("neutron", job):
            files.extend([
                'logs/screen-q-svc.txt',
                ])
        else:
            files.extend([
                'logs/screen-n-net.txt',
                ])
    return files


def format_timedelta(td):
    """Format a timedelta value on seconds boundary."""
    return "%d:%2.2d" % (td.seconds / 60, td.seconds % 60)


class ConsoleNotReady(Exception):
    pass


class FilesNotReady(Exception):
    pass


class ResultTimedOut(Exception):
    pass


class FailJob(object):
    """A single failed job.

    A job is a zuul job.
    """
    bugs = []
    build_short_uuid = None
    url = None
    name = None

    def __init__(self, name, url):
        self.name = name
        self.url = url
        # The last 7 characters of the URL are the first 7 digits
        # of the build_uuid.
        self.build_short_uuid = url[-7:]

    def __str__(self):
        return self.name


class FailEvent(object):
    """A FailEvent consists of one or more FailJobs.

    An event is a gerrit event.
    """
    change = None
    rev = None
    project = None
    url = None
    build_short_uuids = []
    comment = None
    failed_jobs = []

    def __init__(self, event, failed_jobs):
        self.change = int(event['change']['number'])
        self.rev = int(event['patchSet']['number'])
        self.project = event['change']['project']
        self.url = event['change']['url']
        self.comment = event["comment"]
        #TODO(jogo) make FailEvent generate the jobs
        self.failed_jobs = failed_jobs

    def is_openstack_project(self):
        return ("tempest-dsvm-full" in self.comment or
                "gate-tempest-dsvm-virtual-ironic" in self.comment)

    def name(self):
        return "%d,%d" % (self.change, self.rev)

    def bug_urls(self, bugs=None):
        if bugs is None:
            bugs = self.get_all_bugs()
        if not bugs:
            return None
        urls = ['https://bugs.launchpad.net/bugs/%s' % x for
                x in bugs]
        return urls

    def bug_urls_map(self):
        """Produce map of which jobs failed due to which bugs."""
        if not self.get_all_bugs():
            return None
        bug_map = {}
        for job in self.failed_jobs:
            if len(job.bugs) is 0:
                bug_map[job.name] = None
            else:
                bug_map[job.name] = ' '.join(self.bug_urls(job.bugs))
        bug_list = []
        for job in bug_map:
            if bug_map[job] is None:
                bug_list.append("%s: unrecognized error" % job)
            else:
                bug_list.append("%s: %s" % (job, bug_map[job]))
        return bug_list

    def is_fully_classified(self):
        if self.get_all_bugs() is None:
            return True
        for job in self.failed_jobs:
            if len(job.bugs) is 0:
                return False
        return True

    def queue(self):
        # Assume one queue per gerrit event
        if len(self.failed_jobs) == 0:
            return None
        return self.failed_jobs[0].url.split('/')[6]

    def build_short_uuids(self):
        return [job.build_short_uuid for job in self.failed_jobs]

    def failed_job_names(self):
        return [job.name for job in self.failed_jobs]

    def get_all_bugs(self):
        bugs = set([])
        for job in self.failed_jobs:
            bugs |= set(job.bugs)
        if len(bugs) is 0:
            return None
        return list(bugs)


class Stream(object):
    """Gerrit Stream.

    Monitors gerrit stream looking for tempest-devstack failures.
    """

    log = logging.getLogger("recheckwatchbot")

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
            return False

        username = event['author'].get('username', '')
        if (username != 'jenkins'):
            return False

        if not ("Build failed.  For information on how to proceed" in
                event['comment']):
            return False

        failed_tests = []
        for line in event['comment'].split("\n"):
            if " (non-voting)" in line:
                continue
            m = re.search("- ([\w-]+)\s*(http://\S+)\s*:\s*FAILURE", line)
            if m:
                failed_tests.append(FailJob(m.group(1), m.group(2)))
        return failed_tests

    def _job_console_uploaded(self, change, patch, name, build_short_uuid):
        query = qb.result_ready(change, patch, name, build_short_uuid)
        r = self.es.search(query, size='10', recent=True)
        if len(r) == 0:
            msg = ("Console logs not ready for %s %s,%s,%s" %
                   (name, change, patch, build_short_uuid))
            raise ConsoleNotReady(msg)
        else:
            self.log.debug("Console ready for %s %s,%s,%s" %
                           (name, change, patch, build_short_uuid))

    def _has_required_files(self, change, patch, name, build_short_uuid):
        query = qb.files_ready(change, patch, name, build_short_uuid)
        r = self.es.search(query, size='80', recent=True)
        files = [x['term'] for x in r.terms]
        required = required_files(name)
        missing_files = [x for x in required if x not in files]
        if len(missing_files) != 0:
            msg = ("%s missing for %s %s,%s,%s" % (
                missing_files, name, change, patch, build_short_uuid))
            raise FilesNotReady(msg)

    def _does_es_have_data(self, event):
        """Wait till ElasticSearch is ready, but return False if timeout."""
        NUMBER_OF_RETRIES = 20
        SLEEP_TIME = 40
        started_at = datetime.datetime.now()
        # this checks that we've got the console log uploaded, need to retry
        # in case ES goes bonkers on cold data, which it does some times.
        for i in range(NUMBER_OF_RETRIES):
            try:
                for job in event.failed_jobs:
                    #TODO(jogo) if there are three failed jobs and only the
                    #last one isn't ready we don't need to keep rechecking
                    # the first two
                    self._job_console_uploaded(
                        event.change, event.rev, job.name,
                        job.build_short_uuid)
                break

            except ConsoleNotReady as e:
                self.log.debug(e)
                time.sleep(SLEEP_TIME)
                continue
            except pyelasticsearch.exceptions.InvalidJsonResponseError:
                # If ElasticSearch returns an error code, sleep and retry
                # TODO(jogo): if this works pull out search into a helper
                # function that  does this.
                self.log.exception(
                    "Elastic Search not responding on attempt %d" % i)
                time.sleep(SLEEP_TIME)
                continue
        else:
            elapsed = format_timedelta(datetime.datetime.now() - started_at)
            msg = ("Console logs not available after %ss for %s %d,%d,%s" %
                   (elapsed, job.name, event.change, event.rev,
                       job.build_short_uuid))
            raise ResultTimedOut(msg)

        self.log.debug(
            "Found hits for change_number: %d, patch_number: %d"
            % (event.change, event.rev))

        for i in range(NUMBER_OF_RETRIES):
            try:
                for job in event.failed_jobs:
                    self._has_required_files(
                        event.change, event.rev, job.name,
                        job.build_short_uuid)
                self.log.info(
                    "All files present for change_number: %d, patch_number: %d"
                    % (event.change, event.rev))
                time.sleep(10)
                return True
            except FilesNotReady as e:
                self.log.info(e)
                time.sleep(SLEEP_TIME)

        # if we get to the end, we're broken
        elapsed = format_timedelta(datetime.datetime.now() - started_at)
        msg = ("Required files not ready after %ss for %s %d,%d,%s" %
               (elapsed, job.name, event.change, event.rev,
                   job.build_short_uuid))
        raise ResultTimedOut(msg)

    def get_failed_tempest(self):
        self.log.debug("entering get_failed_tempest")
        while True:
            event = self.gerrit.getEvent()

            failed_jobs = Stream.parse_jenkins_failure(event)
            if not failed_jobs:
                # nothing to see here, lets try the next event
                continue

            fevent = FailEvent(event, failed_jobs)

            # bail if it's not an openstack project
            if not fevent.is_openstack_project():
                continue

            self.log.info("Looking for failures in %d,%d on %s" %
                          (fevent.change, fevent.rev,
                          ", ".join(fevent.failed_job_names())))
            if self._does_es_have_data(fevent):
                return fevent

    def leave_comment(self, event, debug=False):
        if event.get_all_bugs():
            message = """I noticed jenkins failed, I think you hit bug(s):

- %(bugs)s
""" % {'bugs': "\n- ".join(event.bug_urls_map())}
            if event.is_fully_classified():
                message += """
We don't automatically recheck or reverify, so please consider
doing that manually if someone hasn't already. For a code review
which is not yet approved, you can recheck by leaving a code
review comment with just the text:

    recheck bug %(bug)s""" % {'bug': list(event.get_all_bugs())[0]}
            else:
                message += """
You have some unrecognized errors."""
            message += """
For bug details see: http://status.openstack.org/elastic-recheck/"""
        else:
            message = ("I noticed jenkins failed, refer to: "
                       "https://wiki.openstack.org/wiki/"
                       "GerritJenkinsGithub#Test_Failures")
        self.log.debug("Compiled comment for commit %s:\n%s" %
                       (event.name(), message))
        if not debug:
            self.gerrit.review(event.project, event.name(), message)


class Classifier():
    """Classify failed tempest-devstack jobs based.

    Given a change and revision, query logstash with a list of known queries
    that are mapped to specific bugs.
    """
    log = logging.getLogger("recheckwatchbot")

    queries = None

    def __init__(self, queries_dir):
        self.es = results.SearchEngine(ES_URL)
        self.queries_dir = queries_dir
        self.queries = loader.load(self.queries_dir)

    def hits_by_query(self, query, queue=None, facet=None, size=100):
        if queue:
            es_query = qb.single_queue(query, queue, facet=facet)
        else:
            es_query = qb.generic(query, facet=facet)
        return self.es.search(es_query, size=size)

    def classify(self, change_number, patch_number,
                 build_short_uuid, recent=False):
        """Returns either empty list or list with matched bugs."""
        self.log.debug("Entering classify")
        #Reload each time
        self.queries = loader.load(self.queries_dir)
        bug_matches = []
        for x in self.queries:
            self.log.debug(
                "Looking for bug: https://bugs.launchpad.net/bugs/%s"
                % x['bug'])
            query = qb.single_patch(x['query'], change_number, patch_number,
                                    build_short_uuid)
            results = self.es.search(query, size='10', recent=recent)
            if len(results) > 0:
                bug_matches.append(x['bug'])
        return bug_matches
