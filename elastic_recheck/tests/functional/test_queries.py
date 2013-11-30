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

from elastic_recheck import elasticRecheck
from elastic_recheck import tests

LPCACHEDIR = os.path.expanduser('~/.launchpadlib/cache')


class TestQueries(tests.TestCase):
    """Make sure queries are valid.

    Make sure all queries are for open OpenStack bugs in Launchpad or have
    hits in logstash.openstack.org.
    This test is used to validate any changes to queries.yaml
    """

    def setUp(self):
        super(TestQueries, self).setUp()
        config = ConfigParser.ConfigParser({'server_password': None})
        config.read('elasticRecheck.conf')
        self.queries = config.get('gerrit', 'query_file')
        self.classifier = elasticRecheck.Classifier(self.queries)

    def test_queries(self):
        for x in self.classifier.queries:
            print("Looking for bug: https://bugs.launchpad.net/bugs/%s"
                  % x['bug'])
            self.assertTrue(
                (self._is_valid_ElasticSearch_query(x) or
                 self._is_valid_launchpad_bug(x['bug'])),
                ("Something is wrong with bug %s" % x['bug']))

    def _is_valid_ElasticSearch_query(self, x):
        query = self.classifier._apply_template(
            self.classifier.general_template,
            x['query'])
        results = self.classifier.es.search(query, size='10')
        valid_query = int(results['hits']['total']) > 0
        if not valid_query:
            print "Didn't find any hits for bug %s" % x['bug']
        return valid_query

    def _is_valid_launchpad_bug(self, bug):
        lp = launchpad.Launchpad.login_anonymously('grabbing bugs',
                                                   'production',
                                                   LPCACHEDIR)
        openstack_group = lp.project_groups['openstack']
        openstack_projects = map(lambda project: project.name,
                                 openstack_group.projects)
        lp_bug = lp.bugs[bug]
        bug_tasks = lp_bug.bug_tasks
        bug_complete = map(lambda bug_task: bug_task.is_complete, bug_tasks)
        projects = map(lambda bug_task: bug_task.bug_target_name, bug_tasks)
        # Check if all open bug tasks are closed if is_complete is true
        # for all tasks.
        if len(bug_complete) != bug_complete.count(True):
            print "bug %s is closed in launchpad" % bug
            return False
        # Check that all bug_tasks are targeted to OpenStack Projects
        for project in projects:
            if project not in openstack_projects:
                print "bug target %s not an openstack project" % project
                return False
        return True
