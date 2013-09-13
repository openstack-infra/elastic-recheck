#!/usr/bin/env python

import gerritlib.gerrit
from pyelasticsearch import ElasticSearch

import ConfigParser
import json


class Stream(object):
    """Gerrit Stream.

    Monitors gerrit stream looking for devstack-tempest failures.
    """

    def __init__(self):
        config = ConfigParser.ConfigParser()
        config.read('elasticRecheck.conf')
        host = 'review.openstack.org'
        user = config.get('gerrit', 'user', 'jogo')
        port = 29418
        self.gerrit = gerritlib.gerrit.Gerrit(host, user, port)
        self.gerrit.startWatching()

    def get_failed_tempest(self):
        while True:
            event = self.gerrit.getEvent()
            if event.get('type', '') != 'comment-added':
                continue
            username = event['author'].get('username', '')
            if (event['author']['username'] == 'jenkins' and
                    "Build failed.  For information on how to proceed" in
                    event['comment']):
                for line in event['comment'].split():
                    if "FAILURE" in line and "tempest-devstack" in line:
                        return event
                continue


class Classifier():
    """Classify failed devstack-tempest jobs based.

    Given a change and revision, query logstash with a list of known queries
    that are mapped to specific bugs.
    """
    ES_URL = "http://logstash.openstack.org/elasticsearch"
    template = {
            "sort": {
                "@timestamp": {"order": "desc"}
                },
            "query": {
                "query_string": {
                    "query": '%s AND @fields.build_change:"%s" AND @fields.build_patchset:"%s"'
                    }
                }
            }
    queries = None

    def __init__(self):
        self.es = ElasticSearch(self.ES_URL)
        self.queries = json.loads(open('queries.json').read())
        for x in self.queries:
            print x['bug']
        #TODO(jogo): import a list of queries from a config file

    def test(self):
        query = self.template.copy()
        query['query']['query_string']['query'] = (query['query']['query_string']['query'] %
            ('@tags:"console.html" AND @message:"Finished: FAILURE"', '34825', '3'))
        results = self.es.search(query, size='10')
        for x in results['hits']['hits']:
            try:
                change = x["_source"]['@fields']['build_change']
                patchset = x["_source"]['@fields']['build_patchset']
                print "build_name %s" % x["_source"]['@fields']['build_name']
                print "https://review.openstack.org/#/c/%(change)s/%(patchset)s" % locals()
            except KeyError:
                print "build_name %s" % x["_source"]['@fields']['build_name']
                pass

    def classify(self, change_number, patch_number):
        """Returns either None or a bug number"""
        #TODO(jogo): implement me
        pass

def main():
    classifier = Classifier()
    #classifier.test()
    stream = Stream()
    while True:
        event = stream.get_failed_tempest()
        change =  event['change']['number']
        rev = event['patchSet']['number']
        print change, rev
        print event['comment']
        bug_number = classifier.classify(change, rev)
        print "======================="
        print "https://review.openstack.org/#/c/%(change)s/%(rev)s" % locals()
        if bug_number is None:
            print "unable to classify failure"
        else:
            print "Found bug: https://bugs.launchpad.net/bugs/%d" % bug_number


if __name__ == "__main__":
    main()
