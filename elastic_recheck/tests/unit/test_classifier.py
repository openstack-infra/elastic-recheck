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

from elastic_recheck import elasticRecheck
from elastic_recheck import loader
from elastic_recheck import results
from elastic_recheck import tests


def fake_queries(*args):
    return [
        {'query': '@message:"fake query" AND @fields.filename:"fake"\n',
         'bug': 1226337},
        {'query': 'magic query',
         'bug': 1234567},
        {'query': '@message:"fake_query3" AND @fields.filename:"fake"\n',
         'bug': 1235437}]


def _fake_search(query, size=None):
    files = ['console.html', 'logs/screen-n-api.txt',
             'logs/screen-n-cpu.txt', 'logs/screen-n-sch.txt',
             'logs/screen-c-api.txt', 'logs/screen-c-vol.txt',
             'logs/syslog.txt']
    file_list = []
    for f in files:
        file_list.append({'term': f})
    log_url = ('http://logs.openstack.org/57/51057/1/gate/gate-tempest-'
               'devstack-vm-full/f8965ee/console.html')
    hit_dict = {'_source': {'@fields': {'log_url': log_url}}}
    if 'magic query' in query['query']['query_string']['query']:
        fake_result = results.ResultSet(
            {'hits': {'total': 2, 'hits': [hit_dict, hit_dict]},
             'facets': {'tag': {'terms': file_list}}})
    else:
        fake_result = results.ResultSet(
            {'hits': {'total': 1, 'hits': [hit_dict]},
             'facets': {'tag': {'terms': file_list}}})
    return fake_result


def _fake_urls_match(comment, results):
    # TODO(sdague): this is not a good fake url work around, however it will
    # get us through the merge in of the new result sets. We'll eventually
    # make this actual life like data.
    if len(results) == 2:
        return True
    else:
        return False


def _fake_is_ready_urls_match(comment, results):
    return True


def _fake_is_ready(change_number, patch_number, comment):
    return True


class TestClassifier(tests.TestCase):

    def setUp(self):
        super(TestClassifier, self).setUp()
        self.stubs.Set(loader, 'load', fake_queries)
        self.classifier = elasticRecheck.Classifier('queries.yaml')

    def test_is_ready(self):
        self.stubs.Set(self.classifier.es, 'search', _fake_search)
        result = self.classifier._is_ready(
            '49282',
            '3',
            'BLAH http://logs.openstack.org/57/51057/1/gate/'
            'gate-tempest-devstack-vm-full/f8965ee'
        )
        self.assertTrue(result)

    def test_classify(self):
        self.stubs.Set(self.classifier.es, 'search', _fake_search)
        self.stubs.Set(self.classifier, '_urls_match', _fake_urls_match)
        self.stubs.Set(self.classifier, '_is_ready', _fake_is_ready)
        bug_numbers = self.classifier.classify(
            '47463',
            '3',
            ' blah http://logs.openstack.org/63/47463/3/gate/gate-tempest'
            '-devstack-vm-postgres-full/99bb8f6'
        )
        self.assertEqual(bug_numbers, [1234567])
