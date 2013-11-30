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

from elastic_recheck import elasticRecheck as er
from elastic_recheck.tests import unit


class TestElasticRecheck(unit.UnitTestCase):
    def test_hits_by_query_no_results(self):
        c = er.Classifier("queries.yaml")
        results = c.hits_by_query("this should find no bugs")
        self.assertEqual(len(results), 0)
        self.assertEqual(results.took, 53)
        self.assertEqual(results.timed_out, False)

    def test_hits_by_query(self):
        c = er.Classifier("queries.yaml")
        q = ('''message:"Cannot ''createImage''"'''
             ''' AND filename:"console.html"''')
        results = c.hits_by_query(q)
        self.assertEqual(len(results), 20)
        self.assertEqual(results.took, 46)
        self.assertEqual(results.timed_out, False)
