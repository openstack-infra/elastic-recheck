#!/usr/bin/env python

# Copyright 2013 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import base64
from datetime import datetime
import json

import elastic_recheck.elasticRecheck as er


def main():
    parser = argparse.ArgumentParser(description='Generate data for graphs.')
    parser.add_argument(dest='queries',
                        help='path to query file')
    parser.add_argument('-o', dest='output',
                        help='output filename')
    args = parser.parse_args()

    classifier = er.Classifier(args.queries)

    buglist = []
    epoch = datetime.utcfromtimestamp(0)

    for query in classifier.queries:
        urlq = dict(search=query['query'],
                    fields=[],
                    offset=0,
                    timeframe="604800",
                    graphmode="count")
        logstash_query = base64.urlsafe_b64encode(json.dumps(urlq))
        bug = dict(number=query['bug'],
                   query=query['query'],
                   logstash_query=logstash_query,
                   data=[])
        buglist.append(bug)
        results = classifier.hits_by_query(query['query'], size=3000)
        histograms = {}
        seen = set()
        for hit in results['hits']['hits']:
            uuid = hit['_source']['@fields']['build_uuid']
            if type(uuid) == list:
                uuid = uuid[0]
            key = '%s-%s' % (uuid, query['bug'])
            if key in seen:
                continue
            seen.add(key)

            ts = datetime.strptime(hit['_source']['@timestamp'],
                                   "%Y-%m-%dT%H:%M:%S.%fZ")
            # hour resolution
            ts = datetime(ts.year, ts.month, ts.day, ts.hour)
            # ms since epoch
            pos = int(((ts - epoch).total_seconds()) * 1000)

            result = hit['_source']['@fields']['build_status']
            if type(result) == list:
                result = hit['_source']['@fields']['build_status'][0]

            if result not in histograms:
                histograms[result] = {}
            hist = histograms[result]

            if pos not in hist:
                hist[pos] = 0
            hist[pos] += 1

        for name, hist in histograms.items():
            d = dict(label=name,
                     data=[])
            positions = hist.keys()
            positions.sort()
            last = None
            for pos in positions:
                if last is not None:
                    prev = pos - 3600000
                    if prev > last:
                        for i in range(last, prev, 3600000):
                            d['data'].append([i, 0])
                d['data'].append([pos, hist[pos]])
                last = pos
            bug['data'].append(d)

    out = open(args.output, 'w')
    out.write(json.dumps(buglist))
    out.close()


if __name__ == "__main__":
    main()
