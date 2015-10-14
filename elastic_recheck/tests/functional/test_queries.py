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
import pyelasticsearch

from elastic_recheck import elasticRecheck
import elastic_recheck.query_builder as qb
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
        if config.has_section('data_source'):
            es_url = config.get('data_source', 'es_url')
            db_uri = config.get('data_source', 'db_uri')
        else:
            es_url = None
            db_uri = None

        if config.has_section('gerrit'):
            self.queries = config.get('gerrit', 'query_file')
        else:
            self.queries = 'queries'

        self.classifier = elasticRecheck.Classifier(self.queries,
                                                    es_url=es_url,
                                                    db_uri=db_uri)

        self.lp = launchpad.Launchpad.login_anonymously('grabbing bugs',
                                                        'production',
                                                        LPCACHEDIR)
        self.openstack_projects = (self.get_group_projects('openstack') +
                                   self.get_group_projects('oslo'))

    def get_group_projects(self, group_name):
        group = self.lp.project_groups[group_name]
        return map(lambda project: project.name,
                   group.projects)

    def test_launchpad(self):
        bad_bugs = []
        for x in self.classifier.queries:
            print("Looking for bug: https://bugs.launchpad.net/bugs/%s"
                  % x['bug'])
            if not self._is_valid_launchpad_bug(x['bug']):
                bad_bugs.append("https://bugs.launchpad.net/bugs/%s" %
                                x['bug'])
        if len(bad_bugs) > 0:
            self.fail("the following bugs are not targeted to openstack "
                      "on launchpad: %s" % bad_bugs)

    def test_elasticsearch_query(self):
        for x in self.classifier.queries:
            print("Looking for bug: https://bugs.launchpad.net/bugs/%s"
                  % x['bug'])
            self.assertTrue(
                self._is_valid_ElasticSearch_query(x, x['bug']),
                ("Something is wrong with bug %s" % x['bug']))

    def _is_valid_ElasticSearch_query(self, x, bug):
        query = qb.generic(x['query'])
        try:
            results = self.classifier.es.search(query, size='10')
        except pyelasticsearch.ElasticHttpError:
            self.fail("Failure to process query for bug %s" % bug)

        valid_query = len(results) > 0
        if not valid_query:
            print("Didn't find any hits for bug %s" % x['bug'])
        # don't fail tests if no hits for a bug
        return True

    def _is_valid_launchpad_bug(self, bug):
        bug_tasks = self.lp.bugs[bug].bug_tasks
        projects = map(lambda bug_task: bug_task.bug_target_name, bug_tasks)
        # Check that at least one bug_tasks is targeted to an OpenStack Project
        for project in projects:
            if '/' in project:
                # project is a specific series, ignore
                continue
            if project in self.openstack_projects:
                return True
        print("bug has no targets in the openstack launchpad group")
        return False
