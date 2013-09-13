#!/usr/bin/env python

import gerritlib.gerrit
from pyelasticsearch import ElasticSearch

import ConfigParser


class Stream(object):
    """Gerrit Stream."""

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
            if (event['author']['username'] == 'jenkins' and
                    "Build failed.  For information on how to proceed" in
                    event['comment']):
                for line in event['comment'].split():
                    if "FAILURE" in line and "tempest-devstack" in line:
                        return event
                continue


class Classifier():
    ES_URL = "http://logstash.openstack.org/elasticsearch"
    tempest_failed_jobs = {
            "sort": {
                "@timestamp": {"order": "desc"}
                },
            "query": {
                "query_string": {
                    "query": '@tags:"console.html" AND @message:"Finished: FAILURE" AND @fields.build_change:"46396" AND @fields.build_patchset:"1"'
                    }
                }
            }

    def __init__(self):
        self.es = ElasticSearch(self.ES_URL)

    def test(self):
        results = self.es.search(self.tempest_failed_jobs, size='10')
        for x in results['hits']['hits']:
            try:
                change = x["_source"]['@fields']['build_change']
                patchset = x["_source"]['@fields']['build_patchset']
                print "https://review.openstack.org/#/c/%(change)s/%(patchset)s" % locals()
            except KeyError:
                print "build_name %s" % x["_source"]['@fields']['build_name']
                pass



def main():
    classifier = Classifier()
    #classifier.test()
    stream = Stream()
    while True:
        event = stream.get_failed_tempest()
        print event['change']['number']
        print event['patchSet']['number']
        print event['comment']


if __name__ == "__main__":
    main()
