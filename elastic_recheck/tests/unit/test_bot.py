# Copyright 2014 IBM Corp.
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
import unittest
import yaml

import fixtures
import mock

from elastic_recheck import bot
from elastic_recheck import elasticRecheck
from elastic_recheck import tests
import elastic_recheck.tests.unit.fake_gerrit as fg


def _set_fake_config(fake_config):
    fake_config.add_section('ircbot')
    fake_config.add_section('gerrit')
    # Set fake ircbot config
    fake_config.set('ircbot', 'nick', 'Fake_User')
    fake_config.set('ircbot', 'pass', '')
    fake_config.set('ircbot', 'server', 'irc.fake.net')
    fake_config.set('ircbot', 'port', 6667)
    fake_config.set('ircbot', 'channel_config',
                    'fake_recheck_watch_bot.yaml')
    # Set fake gerrit config
    fake_config.set('gerrit', 'user', 'fake_user')
    fake_config.set('gerrit', 'query_file', 'fake_query_file')
    fake_config.set('gerrit', 'host', 'fake_host.openstack.org')
    fake_config.set('gerrit', 'key', 'abc123def456')


# NOTE(mtreinish) Using unittest here because testtools TestCase.assertRaises
# doesn't support using it as a context manager
class TestBot(unittest.TestCase):
    def setUp(self):
        super(TestBot, self).setUp()
        self.fake_config = ConfigParser.ConfigParser({'server_password': None})
        _set_fake_config(self.fake_config)
        self.channel_config = bot.ChannelConfig(yaml.load(
            open('recheckwatchbot.yaml')))
        with mock.patch('launchpadlib.launchpad.Launchpad'):
            self.recheck_watch = bot.RecheckWatch(
                None,
                self.channel_config,
                self.fake_config.get('gerrit', 'user'),
                self.fake_config.get('gerrit', 'query_file'),
                self.fake_config.get('gerrit', 'host'),
                self.fake_config.get('gerrit', 'key'),
                False)

    def test_read_channel_config_not_specified(self):
        self.fake_config.set('ircbot', 'channel_config', None)
        with self.assertRaises(bot.ElasticRecheckException) as exc:
            bot._main([], self.fake_config)
        raised_exc = exc.exception
        self.assertEqual(str(raised_exc), "Channel Config must be specified "
                         "in config file.")

    def test_read_channel_config_invalid_path(self):
        self.fake_config.set('ircbot', 'channel_config', 'fake_path.yaml')
        with self.assertRaises(bot.ElasticRecheckException) as exc:
            bot._main([], self.fake_config)
        raised_exc = exc.exception
        error_msg = "Unable to read layout config file at fake_path.yaml"
        self.assertEqual(str(raised_exc), error_msg)

    def test__read_no_event_no_msg(self):
        with self.assertRaises(bot.ElasticRecheckException) as exc:
            self.recheck_watch._read()
        raised_exc = exc.exception
        error_msg = 'No event or msg specified'
        self.assertEqual(str(raised_exc), error_msg)


class TestBotWithTestTools(tests.TestCase):

    def setUp(self):
        super(TestBotWithTestTools, self).setUp()
        self.useFixture(fixtures.MonkeyPatch(
            'gerritlib.gerrit.Gerrit',
            fg.Gerrit))
        self.fake_config = ConfigParser.ConfigParser({'server_password': None})
        _set_fake_config(self.fake_config)
        self.channel_config = bot.ChannelConfig(yaml.load(
            open('recheckwatchbot.yaml')))
        with mock.patch('launchpadlib.launchpad.Launchpad'):
            self.recheck_watch = bot.RecheckWatch(
                None,
                self.channel_config,
                self.fake_config.get('gerrit', 'user'),
                self.fake_config.get('gerrit', 'query_file'),
                self.fake_config.get('gerrit', 'host'),
                self.fake_config.get('gerrit', 'key'),
                False)

    def fake_print(self, channel, msg):
        reference = ("openstack/keystone change: https://review.openstack.org/"
                     "64750 failed because of: "
                     "gate-keystone-python26: "
                     "https://bugs.launchpad.net/bugs/123456, "
                     "gate-keystone-python27: unrecognized error")
        self.assertEqual(reference, msg)

    def fake_display(self, channel, msg):
        return True

    def test_error_found(self):
        self.useFixture(fixtures.MonkeyPatch(
            'elastic_recheck.bot.RecheckWatch.print_msg',
            self.fake_print))
        self.useFixture(fixtures.MonkeyPatch(
            'elastic_recheck.bot.RecheckWatch.display',
            self.fake_display))
        with mock.patch.object(
                elasticRecheck.Stream, '_does_es_have_data') as mock_data:
            mock_data.return_value = True
            stream = elasticRecheck.Stream("", "", "")
            event = stream.get_failed_tempest()
            self.assertIsNone(event.bug_urls_map())
            # Add bugs
            for job in event.failed_jobs:
                if job.name == 'gate-keystone-python26':
                    job.bugs = ['123456']
            self.assertTrue(self.recheck_watch.display('channel', event))
            self.recheck_watch.error_found('channel', event)

    def test_message_config(self):
        data = {'messages': {'test': 'message'}}
        config = bot.MessageConfig(data)
        self.assertEqual(config['test'], data['messages']['test'])
