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


class TestRequiredFiles(testtools.TestCase):
    def test_url(self):
        url = elasticRecheck.RequiredFiles.prep_url('http://logs.openstack.org/13/46613/2/check/gate-tempest-devstack-vm-full/864bf44/console.html')
        self.assertEqual(url,
                         'http://logs.openstack.org/13/46613/2/check/gate-tempest-devstack-vm-full/864bf44')

    def test_files_at_url_pass(self):
        self.assertTrue(elasticRecheck.RequiredFiles.files_at_url('http://logs.openstack.org/13/46613/2/check/gate-tempest-devstack-vm-full/864bf44'))

    def test_files_at_url_fail(self):
        self.assertFalse(elasticRecheck.RequiredFiles.files_at_url('http://logs.openstack.org/02/44502/7/check/gate-tempest-devstack-vm-neutron/4f386e5'))
        self.assertFalse(elasticRecheck.RequiredFiles.files_at_url('http://logs.openstack.org/45/47445/3/check/gate-tempest-devstack-vm-full/0e43e09/'))
