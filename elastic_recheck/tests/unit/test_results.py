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

import datetime
import json

import mock
import pyelasticsearch

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
        self.assertEqual(list(facets.keys()), ['FAILURE'])

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
        print(facets[1382104800000].keys())
        self.assertEqual(list(facets[1382104800000].keys()), ["FAILURE"])
        self.assertEqual(len(facets[1382104800000]["FAILURE"]), 2)
        self.assertEqual(list(facets[1382101200000].keys()), ["FAILURE"])


# NOTE(mriedem): We can't mock built-ins so we have to override utcnow().
class MockDatetimeToday(datetime.datetime):

    @classmethod
    def utcnow(cls):
        # One hour and one second into today.
        return datetime.datetime.strptime('2014-06-12T01:00:01',
                                          '%Y-%m-%dT%H:%M:%S')


class MockDatetimeYesterday(datetime.datetime):

    @classmethod
    def utcnow(cls):
        # 59 minutes and 59 seconds into today.
        return datetime.datetime.strptime('2014-06-12T00:59:59',
                                          '%Y-%m-%dT%H:%M:%S')


@mock.patch.object(pyelasticsearch.ElasticSearch, 'search', return_value={})
class TestSearchEngine(tests.TestCase):
    """Tests that the elastic search API is called correctly."""

    def setUp(self):
        super(TestSearchEngine, self).setUp()
        self.engine = results.SearchEngine('http://fake-url')
        self.query = 'message:"foo" AND tags:"console"'

    def test_search_not_recent(self, search_mock):
        # Tests a basic search with recent=False.
        result_set = self.engine.search(self.query, size=10)
        self.assertEqual(0, len(result_set))
        search_mock.assert_called_once_with(self.query, size=10)

    def _test_search_recent(self, search_mock, datetime_mock,
                            expected_indexes):
        datetime.datetime = datetime_mock
        result_set = self.engine.search(self.query, size=10, recent=True)
        self.assertEqual(0, len(result_set))
        search_mock.assert_called_once_with(
            self.query, size=10, index=expected_indexes)

    def test_search_recent_current_index_only(self, search_mock):
        # The search index comparison goes back one hour and cuts off by day,
        # so test that we're one hour and one second into today so we only have
        # one index in the search call.
        with mock.patch.object(
                pyelasticsearch.ElasticSearch, 'status') as mock_data:
            mock_data.return_value = "Not an exception"
            self._test_search_recent(search_mock, MockDatetimeToday,
                                     expected_indexes=['logstash-2014.06.12'])

    def test_search_recent_multiple_indexes(self, search_mock):
        # The search index comparison goes back one hour and cuts off by day,
        # so test that we're 59 minutes and 59 seconds into today so that we
        # have an index for today and yesterday in the search call.
        with mock.patch.object(
                pyelasticsearch.ElasticSearch, 'status') as mock_data:
            mock_data.return_value = "Not an exception"
            self._test_search_recent(search_mock, MockDatetimeYesterday,
                                     expected_indexes=['logstash-2014.06.12',
                                                       'logstash-2014.06.11'])

    def test_search_no_indexes(self, search_mock):
        # Test when no indexes are valid
        with mock.patch.object(
                pyelasticsearch.ElasticSearch, 'status') as mock_data:
            mock_data.side_effect = pyelasticsearch.exceptions.\
                ElasticHttpNotFoundError()
            self._test_search_recent(search_mock, MockDatetimeYesterday,
                                     expected_indexes=[])

    def test_search_days(self, search_mock):
        # Test when specific days are used.
        with mock.patch.object(
                pyelasticsearch.ElasticSearch, 'status') as mock_data:
            mock_data.return_value = "Not an exception"
            datetime.datetime = MockDatetimeYesterday
            result_set = self.engine.search(self.query, size=10, days=3,
                                            recent=False)
            self.assertEqual(0, len(result_set))
            search_mock.assert_called_once_with(self.query, size=10,
                                                index=['logstash-2014.06.12',
                                                       'logstash-2014.06.11',
                                                       'logstash-2014.06.10'])
