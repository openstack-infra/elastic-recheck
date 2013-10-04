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

import os

import ConfigParser
from launchpadlib import launchpad
import yaml

from elastic_recheck import elasticRecheck
from elastic_recheck import tests

LPCACHEDIR = os.path.expanduser('~/.launchpadlib/cache')


class TestQueries(tests.TestCase):
    def setUp(self):
        super(TestQueries, self).setUp()
        config = ConfigParser.ConfigParser({'server_password': None})
        config.read('elasticRecheck.conf')
        self.queries = config.get('gerrit', 'query_file')
        self.classifier = elasticRecheck.Classifier(self.queries)

    def test_queries(self):
        for x in self.classifier.queries:
            print "Looking for bug: https://bugs.launchpad.net/bugs/%s" % x['bug']
            query = self.classifier._apply_template(self.classifier.general_template, x['query'])
            results = self.classifier.es.search(query, size='10')
            self.assertTrue(int(results['hits']['total']) > 0, ("unable to find hits for bug %s" % x['bug']))

    def test_valid_bugs(self):
        lp = launchpad.Launchpad.login_anonymously('grabbing bugs',
                                                   'production',
                                                   LPCACHEDIR)
        query_dict = yaml.load(open(self.queries).read())
        bugs = map(lambda x: x['bug'], query_dict)
        openstack_group = lp.project_groups['openstack']
        openstack_projects = map(lambda project: project.name,
                                 openstack_group.projects)
        for bug in bugs:
            lp_bug = lp.bugs[bug]
            bug_tasks = lp_bug.bug_tasks
            bug_complete = map(lambda bug_task: bug_task.is_complete, bug_tasks)
            projects = map(lambda bug_task: bug_task.bug_target_name, bug_tasks)
            # Check if all open bug tasks are closed if is_complete is true for all tasks.
            self.assertNotEquals(len(bug_complete), bug_complete.count(True),
                                 "bug %s is closed in launchpad" % bug)
            # Check that all bug_tasks are targetted to OpenStack Projects
            for project in projects:
                self.assertIn(project, openstack_projects)
