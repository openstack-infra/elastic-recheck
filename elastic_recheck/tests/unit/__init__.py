# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import fixtures
import json

from elastic_recheck import loader
import elastic_recheck.tests


def load_empty():
    with open("elastic_recheck/tests/unit/samples/no-results.json") as f:
        return json.load(f)


def load_by_bug(bug):
    with open("elastic_recheck/tests/unit/samples/bug-%s.json" % bug) as f:
        return json.load(f)


class FakeES(object):
    """A fake elastic search interface.

    This provides a stub of the elastic search interface, so we can return
    fake results based on the samples we've already collected to use for
    other unit tests. It does this by building a reverse mapping from our
    queries.yaml file, and grabbing the results we'd find for known bugs.
    """
    def __init__(self, url):
        self._yaml = loader.load('elastic_recheck/tests/unit/queries')
        self._queries = {}
        for item in self._yaml:
            self._queries[item['query'].rstrip()] = item['bug']

    def search(self, query, **kwargs):
        qstring = query['query']['query_string']['query']
        if qstring in self._queries:
            return load_by_bug(self._queries[qstring])
        return load_empty()


class UnitTestCase(elastic_recheck.tests.TestCase):
    def setUp(self):
        super(UnitTestCase, self).setUp()

        self.useFixture(fixtures.MonkeyPatch('pyelasticsearch.ElasticSearch',
                                             FakeES))
