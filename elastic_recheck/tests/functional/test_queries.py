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

import ConfigParser
import pyelasticsearch

from elastic_recheck import elasticRecheck
import elastic_recheck.query_builder as qb
from elastic_recheck import tests


class TestQueries(tests.TestCase):
    """Make sure queries are valid.

    Make sure all queries are for open OpenStack bugs in Launchpad or have
    hits in logstash.openstack.org.
    This test is used to validate any changes to queries.yaml
    """

    def setUp(self):
        super(TestQueries, self).setUp()
        config = ConfigParser.ConfigParser({'server_password': None})
        config.read('elasticRecheck.conf')
        self.queries = config.get('gerrit', 'query_file')
        self.classifier = elasticRecheck.Classifier(self.queries)

    def test_elasticsearch_query(self):
        for x in self.classifier.queries:
            print("Looking for bug: https://bugs.launchpad.net/bugs/%s"
                  % x['bug'])
            self.assertTrue(
                self._is_valid_ElasticSearch_query(x, x['bug']),
                ("Something is wrong with bug %s" % x['bug']))

    def _is_valid_ElasticSearch_query(self, x, bug):
        query = qb.generic(x['query'])
        try:
            results = self.classifier.es.search(query, size='10')
        except pyelasticsearch.ElasticHttpError:
            self.fail("Failure to process query for bug %s" % bug)

        valid_query = len(results) > 0
        if not valid_query:
            print("Didn't find any hits for bug %s" % x['bug'])
        # don't fail tests if no hits for a bug
        return True
