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

import ConfigParser
import gerritlib
import testtools

from elastic_recheck import elasticRecheck


class TestGerritComment(testtools.TestCase):

    def setUp(self):
        super(TestGerritComment, self).setUp()
        config = ConfigParser.ConfigParser({'server_password': None})
        config.read('elasticRecheck.conf')
        self.user = config.get('gerrit', 'user')
        key = config.get('gerrit', 'key')
        host = 'review-dev.openstack.org'
        self.stream = elasticRecheck.Stream(self.user, host, key, thread=False)
        port = 29418
        self.gerrit = gerritlib.gerrit.Gerrit(host, self.user, port)

    @testtools.skip("Skip until Bug 1517730")
    def test_bug_found(self):
        bug_numbers = set(['1223158'])
        project = 'gtest-org/test'
        commit_id = '434,1'
        commit = '434'
        self.stream.leave_comment(project, commit_id, bug_numbers)
        result = self.gerrit.query(commit, comments=True)
        comments = result.get('comments')
        comment = comments[-1]
        self.assertIn(
            "I noticed tempest failed, I think you hit bug(s):",
            comment.get('message'))
        self.assertIn(
            "https://bugs.launchpad.net/bugs/1223158",
            comment.get('message'))

    @testtools.skip("Skip until Bug 1517730")
    def test_bugs_found(self):
        bug_numbers = set(['1223158', '424242'])
        project = 'gtest-org/test'
        commit_id = '781,1'
        commit = '781'
        self.stream.leave_comment(project, commit_id, bug_numbers)
        result = self.gerrit.query(commit, comments=True)
        comments = result.get('comments')
        comment = comments[-1]
        self.assertIn(
            "I noticed tempest failed, I think you hit bug(s):",
            comment.get('message'))
        self.assertIn(
            "https://bugs.launchpad.net/bugs/1223158",
            comment.get('message'))
        self.assertIn(
            "https://bugs.launchpad.net/bugs/424242",
            comment.get('message'))
