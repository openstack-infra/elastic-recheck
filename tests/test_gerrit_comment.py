import ConfigParser
import gerritlib
import testtools

import elasticRecheck


class TestGerritComment(testtools.TestCase):

    def setUp(self):
        super(TestGerritComment, self).setUp()
        config = ConfigParser.ConfigParser({'server_password': None})
        config.read('elasticRecheck.conf')
        self.user = config.get('gerrit', 'user')
        host = 'review-dev.openstack.org'
        self.stream = elasticRecheck.Stream(self.user, host, thread=False)
        port = 29418
        self.gerrit = gerritlib.gerrit.Gerrit(host, self.user, port)

    def test_bug_found(self):
        bug_number = '1223158'
        project = 'gtest-org/test'
        commit_id = '434,1'
        commit = '434'
        self.stream.leave_comment(project, commit_id, bug_number)
        result = self.gerrit.query(commit, comments=True)
        comments = result.get('comments')
        comment = comments[-1]
        self.assertIn("I noticed tempest failed, I think you hit bug https://bugs.launchpad.net/bugs/1223158", comment.get('message'))

    def test_bug_not_found(self):
        project = 'gtest-org/test'
        commit_id = '434,1'
        commit = '434'
        self.stream.leave_comment(project, commit_id)
        result = self.gerrit.query(commit, comments=True)
        comments = result.get('comments')
        comment = comments[-1]
        self.assertIn("https://wiki.openstack.org/wiki/GerritJenkinsGithub#Test_Failures", comment.get('message'))
