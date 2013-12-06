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

import json

from elastic_recheck import results
from elastic_recheck import tests


def load_sample(bug):
    with open("elastic_recheck/tests/unit/samples/bug-%s.json" % bug) as f:
        return json.load(f)


class TestBasicParsing(tests.TestCase):

    def test_basic_parse(self):
        data = load_sample(1191960)
        result_set = results.ResultSet(data)
        self.assertEqual(len(result_set), 144)
        self.assertEqual(result_set.took, 45)

        hit1 = result_set[0]
        self.assertEqual(hit1.build_status, "SUCCESS")
        self.assertEqual(hit1.build_patchset, "3")
        self.assertEqual(hit1.project, "openstack/tempest")
        self.assertEqual(hit1.timestamp, "2013-10-18T17:39:43.966Z")

    def test_full_iteration(self):
        data = load_sample(1240256)
        result_set = results.ResultSet(data)
        self.assertEqual(len(result_set), 95)
        self.assertEqual(result_set.took, 78)

        for result in result_set:
            self.assertEqual(result.build_status, "FAILURE")

    def test_facet_one_level(self):
        data = load_sample(1218391)
        result_set = results.ResultSet(data)
        facets = results.FacetSet()
        facets.detect_facets(result_set, ["build_uuid"])
        self.assertEqual(len(facets.keys()), 20)

        facets = results.FacetSet()
        facets.detect_facets(result_set, ["build_status"])
        self.assertEqual(facets.keys(), ['FAILURE'])

        data = load_sample(1226337)
        result_set = results.ResultSet(data)
        facets = results.FacetSet()
        facets.detect_facets(result_set, ["build_status"])
        self.assertEqual(len(facets.keys()), 2)
        self.assertIn('FAILURE', facets.keys())
        self.assertIn('SUCCESS', facets.keys())
        self.assertEqual(len(facets['FAILURE']), 202)
        self.assertEqual(len(facets['SUCCESS']), 27)

    def test_facet_multi_level(self):
        data = load_sample(1226337)
        result_set = results.ResultSet(data)
        facets = results.FacetSet()
        facets.detect_facets(result_set, ["build_status", "build_uuid"])
        self.assertEqual(len(facets.keys()), 2)
        self.assertEqual(len(facets['FAILURE'].keys()), 12)
        self.assertEqual(len(facets['SUCCESS'].keys()), 3)

    def test_facet_histogram(self):
        data = load_sample(1226337)
        result_set = results.ResultSet(data)
        facets = results.FacetSet()
        facets.detect_facets(result_set,
                             ["timestamp", "build_status", "build_uuid"])
        self.assertEqual(len(facets.keys()), 14)
        print facets[1382104800000].keys()
        self.assertEqual(facets[1382104800000].keys(), ["FAILURE"])
        self.assertEqual(len(facets[1382104800000]["FAILURE"]), 2)
        self.assertEqual(facets[1382101200000].keys(), ["FAILURE"])
