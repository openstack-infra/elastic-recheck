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

import testtools

from elastic_recheck import elasticRecheck


class TestClassifier(testtools.TestCase):

    def setUp(self):
        super(TestClassifier, self).setUp()
        self.classifier = elasticRecheck.Classifier('queries.yaml')

    def test_read_qeuries_file(self):
        self.assertNotEqual(self.classifier.queries, None)

    def test_elasticSearch(self):
        self.classifier.test()
        self.classifier.last_failures()

    def test_ready(self):
        self.assertTrue(self.classifier._is_ready('49282', '3',
            'BLAH http://logs.openstack.org/82/49282/3/gate/gate-tempest-devstack-vm-postgres-full/ffc0540'))

    def test_classify(self):
        bug_numbers = self.classifier.classify('47463', '3',
            ' blah http://logs.openstack.org/63/47463/3/gate/gate-tempest-devstack-vm-postgres-full/99bb8f6')
        self.assertEqual(bug_numbers, [1218391])
