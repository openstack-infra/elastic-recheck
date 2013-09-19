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

import elasticRecheck
import testtools


class TestClassifier(testtools.TestCase):

    def setUp(self):
        super(TestClassifier, self).setUp()
        self.classifier = elasticRecheck.Classifier('queries.json')

    def test_read_qeuries_file(self):
        self.assertNotEqual(self.classifier.queries, None)

    def test_elasticSearch(self):
        self.classifier.test()
        self.classifier.last_failures()

    def test_ready(self):
        self.classifier._wait_till_ready('30043', '34', 'BLAH http://logs.openstack.org/43/30043/34/check/gate-tempest-devstack-vm-full/b852a33')

    def test_classify(self):
        bug_number = self.classifier.classify('43258', '13',
            ' blah http://logs.openstack.org/58/43258/13/check/gate-tempest-devstack-vm-neutron/55a7887')
        self.assertEqual(bug_number, '1211915')
