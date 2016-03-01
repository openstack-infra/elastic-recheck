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
            # check for the allow-nonvoting flag
            if 'allow-nonvoting' in q:
                self.assertNotIn('voting:1', q['query'])
            else:
                self.assertIn('voting:1', q['query'])

    def test_grenade_compat(self):
        # grenade logs are in logs/new/ and logs/old, while devstack is in
        # logs/. To make sure queries will work with both, one should use
        # filename:logs*screen... (no quotes)
        queries = loader.load("queries")

        for q in queries:
            # Use assertTrue because you can specify a custom message
            self.assertTrue("filename:\"logs/screen-" not in q['query'],
                            msg=("for bug %s" % q['bug']))
