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
            event = stream.get_failed_tempest()
            self.assertEqual(event.change, 64750)
            self.assertEqual(event.rev, 6)
            self.assertEqual(event.project, "openstack/keystone")
            self.assertEqual(event.name(), "64750,6")
            self.assertEqual(event.url, "https://review.openstack.org/64750")
            self.assertEqual(sorted(event.build_short_uuids()),
                             ["5dd41fe", "d3fd328"])
            self.assertTrue(event.is_openstack_project())
            self.assertEqual(event.queue(), "gate")
            self.assertEqual(event.bug_urls(), None)
            self.assertEqual(event.bug_urls_map(), None)
            self.assertEqual(sorted(event.failed_job_names()),
                             ['gate-keystone-python26',
                              'gate-keystone-python27'])
            self.assertEqual(event.get_all_bugs(), None)
            self.assertTrue(event.is_fully_classified())

            event = stream.get_failed_tempest()
            self.assertEqual(event.change, 64749)
            self.assertEqual(event.rev, 6)
            self.assertEqual(event.project, "openstack/keystone")
            self.assertEqual(event.name(), "64749,6")
            self.assertEqual(event.url, "https://review.openstack.org/64749")
            self.assertEqual(sorted(event.build_short_uuids()),
                             ["5dd41fe", "d3fd328"])
            self.assertTrue(event.is_openstack_project())
            self.assertEqual(event.queue(), "check")
            self.assertEqual(event.bug_urls(), None)
            self.assertEqual(event.bug_urls_map(), None)
            self.assertEqual(sorted(event.failed_job_names()),
                             ['gate-keystone-python26',
                              'gate-keystone-python27'])
            self.assertEqual(event.get_all_bugs(), None)
            self.assertTrue(event.is_fully_classified())

            event = stream.get_failed_tempest()
            self.assertEqual(event.change, 63078)
            self.assertEqual(event.rev, 19)
            self.assertEqual(event.project, "openstack/horizon")
            self.assertEqual(event.name(), "63078,19")
            self.assertEqual(event.url, "https://review.openstack.org/63078")
            self.assertEqual(event.build_short_uuids(), ["ab07162"])

            event = stream.get_failed_tempest()
            self.assertEqual(event.change, 65361)
            self.assertEqual(event.rev, 2)
            self.assertEqual(event.project, "openstack/requirements")
            self.assertEqual(event.name(), "65361,2")
            self.assertEqual(event.url, "https://review.openstack.org/65361")
            self.assertEqual(event.build_short_uuids(), ["8209fb4"])

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
        job_names = [x.name for x in jobs]
        self.assertIn('check-requirements-integration-dsvm', job_names)
        self.assertIn('check-tempest-dsvm-full', job_names)
        self.assertIn('check-tempest-dsvm-postgres-full', job_names)
        self.assertIn('check-tempest-dsvm-neutron', job_names)

        for job in jobs:
            if job.name == 'check-requirements-integration-dsvm':
                break
        self.assertEqual(job.name, 'check-requirements-integration-dsvm')
        self.assertEqual(job.url,
                         ("http://logs.openstack.org/31/64831/1/check/"
                          "check-requirements-integration-dsvm/135d0b4"))
        self.assertEqual(job.build_short_uuid, '135d0b4')

        self.assertNotIn('gate-requirements-pep8', job_names)
        self.assertNotIn('gate-requirements-python27', job_names)
        self.assertNotIn('gate-requirements-pypy', job_names)
        self.assertNotIn('gate-tempest-dsvm-large-ops', job_names)
        self.assertNotIn('gate-tempest-dsvm-neutron-large-ops', job_names)
        self.assertNotIn('check-grenade-dsvm', job_names)
        self.assertNotIn('check-swift-dsvm-functional', job_names)

    def test_event(self):
        with mock.patch.object(
                elasticRecheck.Stream, '_does_es_have_data') as mock_data:
            mock_data.return_value = True
            stream = elasticRecheck.Stream("", "", "")

            event = stream.get_failed_tempest()
            # Add bugs
            for job in event.failed_jobs:
                if job.name == 'gate-keystone-python26':
                    job.bugs = ['123456']
            self.assertEqual(event.change, 64750)
            self.assertEqual(event.rev, 6)
            self.assertEqual(event.project, "openstack/keystone")
            self.assertEqual(event.name(), "64750,6")
            self.assertEqual(event.url, "https://review.openstack.org/64750")
            self.assertEqual(sorted(event.build_short_uuids()),
                             ["5dd41fe", "d3fd328"])
            self.assertTrue(event.is_openstack_project())
            self.assertEqual(event.queue(), "gate")
            self.assertEqual(event.bug_urls(),
                             ['https://bugs.launchpad.net/bugs/123456'])
            errors = ['gate-keystone-python27: unrecognized error',
                      'gate-keystone-python26: '
                      'https://bugs.launchpad.net/bugs/123456']
            bug_map = event.bug_urls_map()
            for error in errors:
                self.assertIn(error, bug_map)
            self.assertEqual(sorted(event.failed_job_names()),
                             ['gate-keystone-python26',
                              'gate-keystone-python27'])
            self.assertEqual(event.get_all_bugs(), ['123456'])
            self.assertFalse(event.is_fully_classified())

            event = stream.get_failed_tempest()
            # Add bugs
            for job in event.failed_jobs:
                if job.name == 'gate-keystone-python26':
                    job.bugs = ['123456']
            self.assertEqual(event.change, 64749)
            self.assertEqual(event.rev, 6)
            self.assertEqual(event.project, "openstack/keystone")
            self.assertEqual(event.name(), "64749,6")
            self.assertEqual(event.url, "https://review.openstack.org/64749")
            self.assertEqual(sorted(event.build_short_uuids()),
                             ["5dd41fe", "d3fd328"])
            self.assertTrue(event.is_openstack_project())
            self.assertEqual(event.queue(), "check")
            self.assertEqual(event.bug_urls(),
                             ['https://bugs.launchpad.net/bugs/123456'])
            self.assertEqual(event.bug_urls_map(),
                             ['gate-keystone-python26: '
                              'https://bugs.launchpad.net/bugs/123456',
                              'gate-keystone-python27: unrecognized error'])
            self.assertEqual(sorted(event.failed_job_names()),
                             ['gate-keystone-python26',
                              'gate-keystone-python27'])
            self.assertEqual(event.get_all_bugs(), ['123456'])
            self.assertFalse(event.is_fully_classified())
