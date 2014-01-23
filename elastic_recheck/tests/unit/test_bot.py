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

from elastic_recheck import bot


# NOTE(mtreinish) Using unittest here because testtools TestCase.assertRaises
# doesn't support using it as a context manager
class TestBot(unittest.TestCase):

    def setUp(self):
        super(TestBot, self).setUp()
        self.fake_config = ConfigParser.ConfigParser({'server_password': None})
        self._set_fake_config()
        self.channel_config = bot.ChannelConfig(yaml.load(
            open('recheckwatchbot.yaml')))
        self.recheck_watch = bot.RecheckWatch(None, self.channel_config,
                                              self.fake_config.get('gerrit',
                                                                   'user'),
                                              self.fake_config.get(
                                                  'gerrit',
                                                  'query_file'),
                                              self.fake_config.get('gerrit',
                                                                   'host'),
                                              self.fake_config.get('gerrit',
                                                                   'key'),
                                              False)

    def _set_fake_config(self):
        self.fake_config.add_section('ircbot')
        self.fake_config.add_section('gerrit')
        # Set fake ircbot config
        self.fake_config.set('ircbot', 'nick', 'Fake_User')
        self.fake_config.set('ircbot', 'pass', '')
        self.fake_config.set('ircbot', 'server', 'irc.fake.net')
        self.fake_config.set('ircbot', 'port', 6667)
        self.fake_config.set('ircbot', 'channel_config',
                             'fake_recheck_watch_bot.yaml')
        # Set fake gerrit config
        self.fake_config.set('gerrit', 'user', 'fake_user')
        self.fake_config.set('gerrit', 'query_file', 'fake_query_file')
        self.fake_config.set('gerrit', 'host', 'fake_host.openstack.org')
        self.fake_config.set('gerrit', 'key', 'abc123def456')

    def test_read_channel_config_not_specified(self):
        self.fake_config.set('ircbot', 'channel_config', None)
        with self.assertRaises(Exception) as exc:
            bot._main([], self.fake_config)
        raised_exc = exc.exception
        self.assertEquals(str(raised_exc), "Channel Config must be specified "
                          "in config file.")

    def test_read_channel_config_invalid_path(self):
        self.fake_config.set('ircbot', 'channel_config', 'fake_path.yaml')
        with self.assertRaises(Exception) as exc:
            bot._main([], self.fake_config)
        raised_exc = exc.exception
        error_msg = "Unable to read layout config file at fake_path.yaml"
        self.assertEquals(str(raised_exc), error_msg)

    def test__read_no_event_no_msg(self):
        with self.assertRaises(Exception) as exc:
            self.recheck_watch._read()
        raised_exc = exc.exception
        error_msg = 'No event or msg specified'
        self.assertEquals(str(raised_exc), error_msg)
