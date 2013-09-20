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

import elasticRecheck
import testtools


class TestQueries(testtools.TestCase):
    def setUp(self):
        super(TestQueries, self).setUp()
        self.classifier = elasticRecheck.Classifier('queries.json')

    def test_queries(self):
        for x in self.classifier.queries:
            print "Looking for bug: https://bugs.launchpad.net/bugs/%s" % x['bug']
            query = self.classifier._apply_template(self.classifier.general_template, x['query'])
            results = self.classifier.es.search(query, size='10')
            self.assertTrue(int(results['hits']['total']) > 0, ("unable to find hits for bug %s" % x['bug']))
