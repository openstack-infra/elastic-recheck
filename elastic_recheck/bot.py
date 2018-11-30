#! /usr/bin/env python

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


# The configuration file should look like:
"""
[ircbot]
nick=NICKNAME
pass=PASSWORD
server=irc.freenode.net
port=6667
server_password=SERVERPASS
channel_config=/path/to/yaml/config

[gerrit]
user=gerrit2

[data_source[
es_url=URLofELASTICSEARCH
db_uri=SQLALCHEMY_URI_TO_SUBUNIT2SQL
"""

# The yaml channel config should look like:
"""
openstack-qa:
    events:
     - positive
     - negative
"""

import argparse
import daemon
import os
import textwrap
import threading
import time
import yaml

import irc.bot
from launchpadlib import launchpad

import elastic_recheck.config as er_conf
from elastic_recheck import log as logging

LPCACHEDIR = os.path.expanduser('~/.launchpadlib/cache')


try:
    import daemon.pidlockfile
    pid_file_module = daemon.pidlockfile
except Exception:
    # as of python-daemon 1.6 it doesn't bundle pidlockfile anymore
    # instead it depends on lockfile-0.9.1
    import daemon.pidfile
    pid_file_module = daemon.pidfile


class ElasticRecheckException(Exception):
    pass


class RecheckWatchBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channels, config):
        super(RecheckWatchBot, self).__init__(
            [(config.ircbot_server,
              config.ircbot_port,
              config.ircbot_server_password)],
            config.ircbot_nick,
            config.ircbot_nick)
        self.channel_list = channels
        self.nickname = config.ircbot_nick
        self.password = config.ircbot_pass
        self.log = logging.getLogger('recheckwatchbot')

    def on_nicknameinuse(self, c, e):
        self.log.info('Nick previously in use, recovering.')
        c.nick(c.get_nickname() + "_")
        c.privmsg("nickserv", "identify %s " % self.password)
        c.privmsg("nickserv", "ghost %s %s" % (self.nickname, self.password))
        c.privmsg("nickserv", "release %s %s" % (self.nickname, self.password))
        time.sleep(1)
        c.nick(self.nickname)
        self.log.info('Nick previously in use, recovered.')

    def on_welcome(self, c, e):
        self.log.info('Identifying with IRC server.')
        c.privmsg("nickserv", "identify %s " % self.password)
        self.log.info('Identified with IRC server.')
        for channel in self.channel_list:
            c.join(channel)
            self.log.info('Joined channel %s' % channel)
            time.sleep(0.5)

    def send(self, channel, msg):
        self.log.info('Sending "%s" to %s' % (msg, channel))
        # Cheap way to attempt to send fewer than 512 bytes at a time.
        # TODO(clarkb) calculate actual irc overhead and split properly.
        for chunk in textwrap.wrap(msg, 400):
            self.connection.privmsg(channel, chunk)
            time.sleep(0.5)


class RecheckWatch(threading.Thread):
    def __init__(self, ircbot, channel_config, msgs, config=None,
                 commenting=True):
        super(RecheckWatch, self).__init__()
        self.config = config or er_conf.Config()
        self.ircbot = ircbot
        self.channel_config = channel_config
        self.msgs = msgs
        self.log = logging.getLogger('recheckwatchbot')
        self.username = config.gerrit_user
        self.queries = config.gerrit_query_file
        self.host = config.gerrit_host
        self.connected = False
        self.commenting = commenting
        self.key = config.gerrit_host_key
        self.lp = launchpad.Launchpad.login_anonymously('grabbing bugs',
                                                        'production',
                                                        LPCACHEDIR,
                                                        timeout=60)

    def display(self, channel, event):
        display = False
        for project in self._get_bug_projects(event.get_all_bugs()):
            if channel in self.channel_config.projects['all']:
                display = True
                break
            elif project in self.channel_config.projects:
                if channel in self.channel_config.projects[project]:
                    display = True
                    break
        return display

    def new_error(self, channel, event):
        queue = event.queue()
        msg = ('%s change: %s failed %s in the %s queue with'
               ' an unrecognized error' %
               (event.project,
                event.url,
                ', '.join(event.failed_job_names()),
                queue))
        self.print_msg(channel, msg)

    def error_found(self, channel, event):
        msg = ('%s change: %s failed because of: %s' % (
            event.project,
            event.url,
            ", ".join(event.bug_urls_map())))
        if self.display(channel, event):
            self.print_msg(channel, msg)
        else:
            self.log.info("Didn't leave a message on channel %s for %s because"
                          " the bug doesn't target an appropriate project" % (
                              channel, event.url))

    def print_msg(self, channel, msg):
        self.log.info('Compiled Message %s: %s' % (channel, msg))
        if self.ircbot:
            self.ircbot.send(channel, msg)

    def _get_bug_projects(self, bug_numbers):
        projects = []
        for bug in bug_numbers:
            lp_bug = self.lp.bugs[bug]
            project = map(lambda x: (x.bug_target_name), lp_bug.bug_tasks)
            for p in project:
                projects.append(p)
        return set(projects)

    def _read(self, event=None, msg=""):
        for channel in self.channel_config.channels:
            if msg:
                if channel in self.channel_config.events['negative']:
                    self.print_msg(channel, msg)
            elif event:
                # only display events on gate queue, others are just spam
                if event.queue() == "gate":
                    if event.get_all_bugs():
                        if channel in self.channel_config.events['positive']:
                            self.error_found(channel, event)
                    else:
                        if channel in self.channel_config.events['negative']:
                            self.new_error(channel, event)
            else:
                raise ElasticRecheckException('No event or msg specified')

    def run(self):
        # Import here because it needs to happen after daemonization
        import elastic_recheck.elasticRecheck as er
        classifier = er.Classifier(self.queries, config=self.config)
        stream = er.Stream(self.username, self.host, self.key,
                           config=self.config)
        while True:
            try:
                event = stream.get_failed_tempest()

                for job in event.failed_jobs:
                    job.bugs = set(classifier.classify(
                        event.change,
                        event.rev,
                        job.build_short_uuid,
                        recent=True))
                if not event.get_all_bugs():
                    self._read(event)
                else:
                    self._read(event)
                    stream.leave_comment(
                        event,
                        self.msgs,
                        debug=not self.commenting)
            except er.ResultTimedOut as e:
                self.log.warning(e.message)
                self._read(msg=e.message)
            except Exception:
                self.log.exception("Uncaught exception processing event.")


class MessageConfig(dict):
    def __init__(self, data):
        super(MessageConfig, self).__init__()
        self.update(data['messages'])


class ChannelConfig(object):
    def __init__(self, data):
        # for compatibility reasons we support a pre channel hierarchy
        # model of the world.
        if 'channels' in data:
            data = data['channels']

        self.data = data

        keys = data.keys()
        for key in keys:
            if key[0] != '#':
                data['#' + key] = data.pop(key)
        self.channels = data.keys()
        self.events = {}
        for channel, val in self.data.items():
            for event in val['events']:
                event_set = self.events.get(event, set())
                event_set.add(channel)
                self.events[event] = event_set
        self.projects = {}
        for channel, val in self.data.items():
            for project in val['projects']:
                project_set = self.projects.get(project, set())
                project_set.add(channel)
                self.projects[project] = project_set


def get_options():
    parser = argparse.ArgumentParser(
        description="IRC bot for elastic recheck bug reporting")
    parser.add_argument('-f', '--foreground',
                        default=False,
                        action='store_true',
                        help="Run in foreground")
    parser.add_argument('-n', '--nocomment',
                        default=False,
                        action='store_true',
                        help="Don't comment in gerrit. Useful in testing.")
    parser.add_argument('--noirc',
                        default=False,
                        action='store_true',
                        help="Don't comment in irc. Useful in testing.")
    parser.add_argument('conffile', nargs=1, help="Configuration file")
    return parser.parse_args()


def _main(args, config):
    logging.setup_logging(config)

    fp = config.ircbot_channel_config
    if fp:
        fp = os.path.expanduser(fp)
        if not os.path.exists(fp):
            raise ElasticRecheckException(
                "Unable to read layout config file at %s" % fp)
    else:
        raise ElasticRecheckException(
            "Channel Config must be specified in config file.")

    channel_config = ChannelConfig(yaml.load(open(fp)))
    msgs = MessageConfig(yaml.load(open(fp)))

    if not args.noirc:
        bot = RecheckWatchBot(
            channel_config.channels,
            config=config)
    else:
        bot = None

    recheck = RecheckWatch(
        bot,
        channel_config,
        msgs,
        config=config,
        commenting=not args.nocomment,
    )

    recheck.start()
    if not args.noirc:
        bot.start()


def main():
    args = get_options()

    config = er_conf.Config(config_file=args.conffile)

    if args.foreground:
        _main(args, config)
    else:
        pid = pid_file_module.TimeoutPIDLockFile(config.pid_fn, 10)
        with daemon.DaemonContext(pidfile=pid):
            _main(args, config)


if __name__ == "__main__":
    main()
