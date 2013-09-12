#!/usr/bin/python
from pyelasticsearch import ElasticSearch

ES_URL = "http://logstash.openstack.org/elasticsearch"

es = ElasticSearch(ES_URL)


tempest_failed_jobs = {
    "sort": {
        "@timestamp": {"order": "desc"}
        },
    "query": {
        "query_string": {
            "query": '@tags:"console.html" AND @message:"Finished: FAILURE"'
            }
        }
    }
results = es.search(tempest_failed_jobs, size='10')
for x in results['hits']['hits']:
    try:
        change = x["_source"]['@fields']['build_change']
        patchset = x["_source"]['@fields']['build_patchset']
        print x["_source"]['@timestamp']
        print "https://review.openstack.org/#/c/%(change)s/%(patchset)s" % locals()
    except KeyError:
        print "build_name %s" % x["_source"]['@fields']['build_name']
        pass
