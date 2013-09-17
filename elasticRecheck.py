#!/usr/bin/env python

import gerritlib.gerrit
from pyelasticsearch import ElasticSearch

import ConfigParser
import copy
import json
import logging
import time

logging.basicConfig()

class Stream(object):
    """Gerrit Stream.

    Monitors gerrit stream looking for tempest-devstack failures.
    """

    def __init__(self, user):
        host = 'review.openstack.org'
        port = 29418
        self.gerrit = gerritlib.gerrit.Gerrit(host, user, port)
        self.gerrit.startWatching()

    def get_failed_tempest(self):
        while True:
            event = self.gerrit.getEvent()
            if event.get('type', '') != 'comment-added':
                continue
            username = event['author'].get('username', '')
            if (username  == 'jenkins' and
                    "Build failed.  For information on how to proceed" in
                    event['comment']):
                found = False
                for line in event['comment'].split('\n'):
                    if "FAILURE" in line and "python2" in line:
                        # Unit Test Failure
                        continue
                    if "FAILURE" in line and "tempest-devstack" in line:
                        found = True
                if found:
                    return event
                continue


class Classifier():
    """Classify failed tempest-devstack jobs based.

    Given a change and revision, query logstash with a list of known queries
    that are mapped to specific bugs.
    """
    ES_URL = "http://logstash.openstack.org/elasticsearch"
    targeted_template = {
            "sort": {
                "@timestamp": {"order": "desc"}
                },
            "query": {
                "query_string": {
                    "query": '%s AND @fields.build_change:"%s" AND @fields.build_patchset:"%s"'
                    }
                }
            }
    ready_template = {
            "sort": {
                "@timestamp": {"order": "desc"}
                },
            "query": {
                "query_string": {
                    "query": '@tags:"console.html" AND (@message:"Finished: FAILURE") AND @fields.build_change:"%s" AND @fields.build_patchset:"%s"'
                    #"query": '@fields.filename:"console.html" AND @fields.build_status:"FAILURE" AND @message:"skipped" AND @message:"FAILED (failures" AND @fields.build_change:"%s" AND @fields.build_patchset:"%s"'
                    }
                }
            }
    general_template = {
            "sort": {
                "@timestamp": {"order": "desc"}
                },
            "query": {
                "query_string": {
                    "query": '%s'
                    }
                }
            }

    queries = None

    def __init__(self):
        self.es = ElasticSearch(self.ES_URL)
        self.queries = json.loads(open('queries.json').read())

    def _apply_template(self, template, values):
        query = copy.deepcopy(template)
        query['query']['query_string']['query'] = query['query']['query_string']['query'] % values
        return query

    def test(self):
        query = self._apply_template(self.targeted_template, ('@tags:"console.html" AND @message:"Finished: FAILURE"', '34825', '3'))
        results = self.es.search(query, size='10')
        print results['hits']['total']
        self._parse_results(results)

    def last_failures(self):
        for x in self.queries:
            print "Looking for bug: https://bugs.launchpad.net/bugs/%s" % x['bug']
            query = self._apply_template(self.general_template, x['query'])
            results = self.es.search(query, size='10')
            self._parse_results(results)

    def _parse_results(self, results):
        for x in results['hits']['hits']:
            try:
                change = x["_source"]['@fields']['build_change']
                patchset = x["_source"]['@fields']['build_patchset']
                print "build_name %s" % x["_source"]['@fields']['build_name']
                print "https://review.openstack.org/#/c/%(change)s/%(patchset)s" % locals()
            except KeyError:
                print "build_name %s" % x["_source"]['@fields']['build_name']

    def classify(self, change_number, patch_number, comment):
        """Returns either None or a bug number"""
        #Reload each time
        self.queries = json.loads(open('queries.json').read())
        #Wait till Elastic search is ready
        query = self._apply_template(self.ready_template, (change_number, patch_number))
        while True:
            results = self.es.search(query, size='1')
            if results['hits']['total'] > 0:
                    break
            else:
                time.sleep(40)
            # Just because one file is parsed doesn't mean all are, so wait a
            # bit
            time.sleep(40)
        for x in self.queries:
            print "Looking for bug: https://bugs.launchpad.net/bugs/%s" % x['bug']
            query = self._apply_template(self.targeted_template, (x['query'],
                    change_number, patch_number))
            results = self.es.search(query, size='10')
            for result in results['hits']['hits']:
                url = result["_source"]['@fields']['log_url']
                if self._prep_url(url) in comment:
                    return x['bug']

    def _prep_url(self, url):
        if "/logs/" in url:
            return '/'.join(url.split('/')[:-2])
        return '/'.join(url.split('/')[:-1])


def main():
    classifier = Classifier()
    #classifier.test()
    config = ConfigParser.ConfigParser()
    user = config.get('gerrit', 'user', 'jogo')
    stream = Stream(user)
    while True:
        event = stream.get_failed_tempest()
        change = event['change']['number']
        rev = event['patchSet']['number']
        print "======================="
        print "https://review.openstack.org/#/c/%(change)s/%(rev)s" % locals()
        bug_number = classifier.classify(change, rev, event['comment'])
        if bug_number is None:
            print "unable to classify failure"
        else:
            print "Found bug: https://bugs.launchpad.net/bugs/%s" % bug_number

if __name__ == "__main__":
    main()
