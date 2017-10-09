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

from elastic_recheck.cmd import graph
from elastic_recheck.tests import unit


class FakeResponse(object):
    def __init__(self, response_text, status_code=200):
        super(FakeResponse, self).__init__()
        # magic gerrit prefix
        self.text = ")]}'\n" + response_text
        self.status_code = status_code


class TestGraphCmd(unit.UnitTestCase):
    def test_get_open_reviews_empty(self):
        with mock.patch('requests.get') as mock_get:
            mock_get.return_value = FakeResponse("[]\n")
            self.assertEqual(graph.get_open_reviews('1353131'), [])
        mock_get.assert_called_once()

    def test_get_open_reviews(self):
        with mock.patch('requests.get') as mock_get:
            with open('elastic_recheck/tests/unit/samples/'
                      'gerrit-bug-query.json') as f:
                mock_get.return_value = FakeResponse(f.read())
            self.assertEqual(graph.get_open_reviews('1288393'), [113009])

    def test_get_open_reviews_502_retry(self):
        """Tests that we retry if we get a 502 response from the server."""
        with mock.patch('requests.get') as mock_get:
            mock_get.side_effect = (
                FakeResponse("bad proxy gateway", status_code=502),
                FakeResponse("[]\n"))
            self.assertEqual(graph.get_open_reviews('1353131'), [])
        # We call twice because we retried once.
        self.assertEqual(2, mock_get.call_count)
