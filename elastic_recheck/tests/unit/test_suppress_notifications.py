#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

import mock

from elastic_recheck import elasticRecheck
from elastic_recheck import tests


class TestSuppressNotifcation(tests.TestCase):

    def setUp(self):
        super(TestSuppressNotifcation, self).setUp()
        self.classifier = elasticRecheck.Classifier(
            "./elastic_recheck/tests/unit/suppressed_queries")

    @mock.patch('elastic_recheck.query_builder.single_patch')
    @mock.patch('elastic_recheck.results.SearchEngine.search')
    def test_basic_parse(self, mock1, mock2):
        self.classifier.classify(None, None, None)
        self.assertFalse(mock1.called)
        self.assertFalse(mock2.called)
