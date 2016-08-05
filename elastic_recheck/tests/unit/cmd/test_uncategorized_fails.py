# Copyright 2015 IBM Corp.
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

import uuid

import mock
import testtools

from elastic_recheck.cmd import uncategorized_fails as fails


class TestUncategorizedFails(testtools.TestCase):
    """Tests the uncategorized fails command module"""

    def test_all_fails(self):
        # Tests that we properly filter out results using our blacklist regex.

        # The list of results would really be Hit objects but the attr stuff
        # in those is tricky so let's just be lazy and use mock.
        results = [
            # should be excluded
            mock.MagicMock(build_uuid=str(uuid.uuid4()),
                           build_name='gate-api-site-tox-checklinks',
                           project='openstack/api-site',
                           timestamp='2015-09-25T17:55:09.372Z',
                           log_url='http://logs.openstack.org/1/console.html'),
            # should be excluded
            mock.MagicMock(build_uuid=str(uuid.uuid4()),
                           build_name='gate-openstack-ansible-dsvm-commit',
                           project='openstack/openstack-ansible',
                           timestamp='2015-09-25T17:55:09.372Z',
                           log_url='http://logs.openstack.org/2/console.html'),
            # should be included
            mock.MagicMock(build_uuid=str(uuid.uuid4()),
                           build_name='gate-tempest-dsvm-full',
                           project='openstack/cinder',
                           timestamp='2015-09-25T17:55:09.372Z',
                           log_url='http://logs.openstack.org/3/console.html'),
        ]
        classifier = mock.MagicMock()
        query_mock = mock.Mock(return_value=results)
        classifier.hits_by_query = query_mock
        all_fails = fails.all_fails(classifier)
        # assert that we only have the single result
        self.assertThat(all_fails,
                        testtools.matchers.HasLength(2))
        self.assertThat(all_fails['integrated_gate'],
                        testtools.matchers.HasLength(1))
        self.assertIn('gate-tempest-dsvm-full',
                      all_fails['integrated_gate'].keys()[0])
