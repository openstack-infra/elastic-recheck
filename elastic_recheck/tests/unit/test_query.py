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
import StringIO
import sys

import mock

from elastic_recheck.cmd import query
from elastic_recheck.results import ResultSet
from elastic_recheck.tests import unit


class TestQueryCmd(unit.UnitTestCase):
    def setUp(self):
        super(TestQueryCmd, self).setUp()
        self._stdout = sys.stdout
        sys.stdout = StringIO.StringIO()

    def tearDown(self):
        super(TestQueryCmd, self).tearDown()
        sys.stdout = self._stdout

    def test_query(self):
        with open('elastic_recheck/tests/unit/logstash/1284371.analysis') as f:
            expected_stdout = f.read()
        with mock.patch('elastic_recheck.results.SearchEngine.search') as \
                mock_search:
            with open('elastic_recheck/tests/unit/logstash/1284371.json') as f:
                jsonResponse = json.loads(f.read())
                mock_search.return_value = ResultSet(jsonResponse)
            query.query('elastic_recheck/tests/unit/queries/1284371.yaml')
            sys.stdout.seek(0)
            self.assertEqual(expected_stdout, sys.stdout.read())
