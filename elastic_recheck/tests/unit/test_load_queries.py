# Copyright 2014 Samsung Electronics. All Rights Reserved.
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

from elastic_recheck import loader
from elastic_recheck import tests


class TestLoadQueries(tests.TestCase):
    """Test that all the production queries can be loaded.

    This ensures that we don't completely explode on some badly formed
    yaml that's provided to us.
    """
    def test_load_queries(self):
        queries = loader.load("queries")

        self.assertGreater(len(queries), 0)
        for q in queries:
            self.assertIsNotNone(q['bug'])
            self.assertIsNotNone(q['query'])

    def test_load_queries_all(self):
        queries = loader.load("queries", skip_resolved=False)

        # Note(sdague): the current number of queries, if you delete a file
        # you will need to change this
        self.assertGreater(len(queries), 59)
        for q in queries:
            self.assertIsNotNone(q['bug'])
            self.assertIsNotNone(q['query'])
