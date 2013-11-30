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

import urllib2

from elastic_recheck import elasticRecheck
from elastic_recheck import tests


class TestRequiredFiles(tests.TestCase):
    def test_url(self):
        url = elasticRecheck.RequiredFiles.prep_url(
            'http://logs.openstack.org/13/46613/2/check/'
            'gate-tempest-devstack-vm-full/864bf44/console.html')
        self.assertEqual(
            url,
            'http://logs.openstack.org/13/46613/2/check/'
            'gate-tempest-devstack-vm-full/864bf44')

    def _fake_urlopen(self, url):
        pass

    def test_files_at_url_pass(self):
        self.stubs.Set(urllib2, 'urlopen', self._fake_urlopen)
        result = elasticRecheck.RequiredFiles.files_at_url(
            'http://logs.openstack.org/13/46613/2/check/'
            'gate-tempest-devstack-vm-full/864bf44')
        self.assertTrue(result)

    def _invalid_url_open(self, url):
        raise urllib2.HTTPError(url, 404, 'NotFound', '', None)

    def test_files_at_url_fail(self):
        self.stubs.Set(urllib2, 'urlopen', self._invalid_url_open)
        self.assertFalse(elasticRecheck.RequiredFiles.files_at_url(
            'http://logs.openstack.org/02/44502/7/check/'
            'gate-tempest-devstack-vm-neutron/4f386e5'))
        self.assertFalse(elasticRecheck.RequiredFiles.files_at_url(
            'http://logs.openstack.org/45/47445/3/check/'
            'gate-tempest-devstack-vm-full/0e43e09/'))
