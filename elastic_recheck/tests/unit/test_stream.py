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

import json

import fixtures
import mock

from elastic_recheck import elasticRecheck
from elastic_recheck import tests
import elastic_recheck.tests.unit.fake_gerrit as fg


class TestStream(tests.TestCase):

    def setUp(self):
        super(TestStream, self).setUp()
        self.useFixture(fixtures.MonkeyPatch(
            'gerritlib.gerrit.Gerrit',
            fg.Gerrit))

    def test_gerrit_stream(self):
        """Tests that we can use our mock gerrit to process events."""
        with mock.patch.object(
                elasticRecheck.Stream, '_does_es_have_data') as mock_data:
            mock_data.return_value = True
            stream = elasticRecheck.Stream("", "", "")

            # there are currently 10 events in the stream, 3 are
            # failures
            for i in xrange(3):
                event = stream.get_failed_tempest()
                self.assertEqual(event['author']['username'], 'jenkins')
                self.assertIn('Build failed', event['comment'])
            self.assertRaises(
                fg.GerritDone,
                stream.get_failed_tempest)

    def test_gerrit_parsing(self):
        with open("elastic_recheck/tests/unit/jenkins/events.json") as f:
            j = json.load(f)
            events = j['events']

        self.assertFalse(
            elasticRecheck.Stream.parse_jenkins_failure(events[1]))
        self.assertFalse(
            elasticRecheck.Stream.parse_jenkins_failure(events[2]))

        jobs = elasticRecheck.Stream.parse_jenkins_failure(events[0])
        self.assertIn('check-requirements-integration-dsvm', jobs)
        self.assertIn('check-tempest-dsvm-full', jobs)
        self.assertIn('check-tempest-dsvm-postgres-full', jobs)
        self.assertIn('check-tempest-dsvm-neutron', jobs)

        self.assertEqual(jobs['check-requirements-integration-dsvm'],
                         "http://logs.openstack.org/31/64831/1/check/"
                         "check-requirements-integration-dsvm/135d0b4")

        self.assertNotIn('gate-requirements-pep8', jobs)
        self.assertNotIn('gate-requirements-python27', jobs)
        self.assertNotIn('gate-requirements-pypy', jobs)
        self.assertNotIn('gate-tempest-dsvm-large-ops', jobs)
        self.assertNotIn('gate-tempest-dsvm-neutron-large-ops', jobs)
        self.assertNotIn('check-grenade-dsvm', jobs)
        self.assertNotIn('check-swift-dsvm-functional', jobs)
