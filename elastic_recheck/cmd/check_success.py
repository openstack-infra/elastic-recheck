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

import argparse

import elastic_recheck.elasticRecheck as er


def get_options():
    parser = argparse.ArgumentParser(description='Edit hiera yaml.')
    parser.add_argument('--file', '-f', help="Queries file",
                        default="queries.yaml")
    return parser.parse_args()


def collect_metrics(classifier):
    data = {}
    for q in classifier.queries:
        results = classifier.hits_by_query(q['query'], size=3000)
        rate = {}
        for hit in results:
            uuid = hit.build_uuid
            success = hit.build_status

            if success not in rate:
                rate[success] = set(uuid)
            else:
                rate[success].add(uuid)

        num_fails = 0
        if "FAILURE" in rate:
            num_fails = len(rate["FAILURE"])

        data[q['bug']] = {
            'fails': num_fails,
            'hits': rate,
            'query': q['query']
            }

    return data


def print_metrics(data):
    print "Elastic recheck known issues"

    sorted_data = sorted(data.iteritems(),
                         key=lambda x: -x[1]['fails'])
    for d in sorted_data:
        print "Bug: %s => %s" % (d[0], d[1]['query'].rstrip())
        for s in d[1]['hits'].keys():
            print "  %s: %s" % (s, len(d[1]['hits'][s]))
        print


def main():
    opts = get_options()
    classifier = er.Classifier(opts.file)
    data = collect_metrics(classifier)
    print_metrics(data)


if __name__ == "__main__":
    main()
