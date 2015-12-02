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

import mock

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
             ''' AND filename:"console.html" AND voting:1''')
        results = c.hits_by_query(q)
        self.assertEqual(len(results), 20)
        self.assertEqual(results.took, 46)
        self.assertEqual(results.timed_out, False)


class TestSubunit2sqlCrossover(unit.UnitTestCase):

    @mock.patch(
        'subunit2sql.db.api.get_failing_test_ids_from_runs_by_key_value',
        return_value=['test1', 'test2', 'test3'])
    def test_check_failed_test_ids_for_job_matches(self, mock_db_api):
        res = er.check_failed_test_ids_for_job('fake_uuid',
                                               ['test1', 'test4'],
                                               mock.sentinel.session)
        self.assertTrue(res)

    @mock.patch(
        'subunit2sql.db.api.get_failing_test_ids_from_runs_by_key_value',
        return_value=['test23', 'test12', 'test300'])
    def test_check_failed_test_ids_for_job_no_matches(self, mock_db_api):
        res = er.check_failed_test_ids_for_job('fake_uuid',
                                               ['test1', 'test4'],
                                               mock.sentinel.session)
        self.assertFalse(res)

    @mock.patch.object(er, 'check_failed_test_ids_for_job', return_value=True)
    def test_classify_with_test_id_filter_match(self, mock_id_check):
        c = er.Classifier('./elastic_recheck/tests/unit/queries_with_filters')
        es_mock = mock.patch.object(c.es, 'search', return_value=[1, 2, 3])
        es_mock.start()
        self.addCleanup(es_mock.stop)
        res = c.classify(1234, 1, 'fake')
        self.assertEqual(res, ['1234567'],
                         "classify() returned %s when it should have returned "
                         "a list with one bug id: '1234567'" % res)

    @mock.patch.object(er, 'check_failed_test_ids_for_job', return_value=False)
    def test_classify_with_test_id_filter_no_match(self, mock_id_check):
        c = er.Classifier('./elastic_recheck/tests/unit/queries_with_filters')
        es_mock = mock.patch.object(c.es, 'search', return_value=[1, 2, 3])
        es_mock.start()
        self.addCleanup(es_mock.stop)
        res = c.classify(1234, 1, 'fake')
        self.assertEqual(res, [],
                         "classify() returned bug matches %s when none should "
                         "have been found" % res)
