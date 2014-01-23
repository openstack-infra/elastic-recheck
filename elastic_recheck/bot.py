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
"""

# The yaml channel config should look like:
"""
openstack-qa:
    events:
     - positive
     - negative
"""

import argparse
import ConfigParser
import daemon
import logging
import logging.config
import os
import threading
import time
import yaml

import irc.bot

try:
    import daemon.pidlockfile
    pid_file_module = daemon.pidlockfile
except Exception:
    # as of python-daemon 1.6 it doesn't bundle pidlockfile anymore
    # instead it depends on lockfile-0.9.1
    import daemon.pidfile
    pid_file_module = daemon.pidfile

LOG = logging.getLogger('recheckwatchbot')


class RecheckWatchBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channels, nickname, password, server, port=6667,
                 server_password=None):
        super(RecheckWatchBot, self).__init__(
            [(server, port, server_password)], nickname, nickname)
        self.channel_list = channels
        self.nickname = nickname
        self.password = password

    def on_nicknameinuse(self, c, e):
        LOG.info('Nick previously in use, recovering.')
        c.nick(c.get_nickname() + "_")
        c.privmsg("nickserv", "identify %s " % self.password)
        c.privmsg("nickserv", "ghost %s %s" % (self.nickname, self.password))
        c.privmsg("nickserv", "release %s %s" % (self.nickname, self.password))
        time.sleep(1)
        c.nick(self.nickname)
        LOG.info('Nick previously in use, recovered.')

    def on_welcome(self, c, e):
        LOG.info('Identifying with IRC server.')
        c.privmsg("nickserv", "identify %s " % self.password)
        LOG.info('Identified with IRC server.')
        for channel in self.channel_list:
            c.join(channel)
            LOG.info('Joined channel %s' % channel)
            time.sleep(0.5)

    def send(self, channel, msg):
        LOG.info('Sending "%s" to %s' % (msg, channel))
        self.connection.privmsg(channel, msg)
        time.sleep(0.5)


class RecheckWatch(threading.Thread):
    def __init__(self, ircbot, channel_config, username,
                 queries, host, key, commenting=True):
        super(RecheckWatch, self).__init__()
        self.ircbot = ircbot
        self.channel_config = channel_config
        self.username = username
        self.queries = queries
        self.host = host
        self.connected = False
        self.commenting = commenting
        self.key = key

    def new_error(self, channel, event):
        msg = '%s change: %s failed with an unrecognized error' % (
            event.project, event.url)
        self.print_msg(channel, msg)

    def error_found(self, channel, event):
        msg = ('%s change: %s failed tempest because of: %s' % (
            event.project, event.url, event.bug_urls()))
        self.print_msg(channel, msg)

    def print_msg(self, channel, msg):
        LOG.info('Compiled Message %s: %s' % (channel, msg))
        if self.ircbot:
            self.ircbot.send(channel, msg)

    def _read(self, event, msg=""):
        for channel in self.channel_config.channels:
            if msg:
                if channel in self.channel_config.events['negative']:
                    self.print_msg(channel, msg)
            elif event.bugs:
                if channel in self.channel_config.events['positive']:
                    self.error_found(channel, event)
            else:
                if channel in self.channel_config.events['negative']:
                    self.new_error(channel, event)

    def run(self):
        # Import here because it needs to happen after daemonization
        import elastic_recheck.elasticRecheck as er
        classifier = er.Classifier(self.queries)
        stream = er.Stream(self.username, self.host, self.key)
        while True:
            try:
                event = stream.get_failed_tempest()

                event.bugs = classifier.classify(event.change, event.rev)
                if not event.bugs:
                    self._read(event)
                else:
                    self._read(event)
                    if self.commenting:
                        stream.leave_comment(
                            event.project,
                            event.name(),
                            event.bugs)
            except er.ResultTimedOut as e:
                LOG.warn(e.msg)
                self._read(msg=e.msg)
            except Exception:
                LOG.exception("Uncaught exception processing event.")


class ChannelConfig(object):
    def __init__(self, data):
        self.data = data
        keys = data.keys()
        for key in keys:
            if key[0] != '#':
                data['#' + key] = data.pop(key)
        self.channels = data.keys()
        self.events = {}
        for channel, val in self.data.iteritems():
            for event in val['events']:
                event_set = self.events.get(event, set())
                event_set.add(channel)
                self.events[event] = event_set


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
    setup_logging(config)

    fp = config.get('ircbot', 'channel_config')
    if fp:
        fp = os.path.expanduser(fp)
        if not os.path.exists(fp):
            raise Exception("Unable to read layout config file at %s" % fp)
    else:
        raise Exception("Channel Config must be specified in config file.")

    channel_config = ChannelConfig(yaml.load(open(fp)))

    if not args.noirc:
        bot = RecheckWatchBot(
            channel_config.channels,
            config.get('ircbot', 'nick'),
            config.get('ircbot', 'pass'),
            config.get('ircbot', 'server'),
            config.getint('ircbot', 'port'),
            config.get('ircbot', 'server_password'))
    else:
        bot = None

    recheck = RecheckWatch(
        bot,
        channel_config,
        config.get('gerrit', 'user'),
        config.get('gerrit', 'query_file'),
        config.get('gerrit', 'host', 'review.openstack.org'),
        config.get('gerrit', 'key'),
        not args.nocomment
    )

    recheck.start()
    if not args.noirc:
        bot.start()


def main():
    args = get_options()

    config = ConfigParser.ConfigParser({'server_password': None})
    config.read(args.conffile)

    if config.has_option('ircbot', 'pidfile'):
        pid_fn = os.path.expanduser(config.get('ircbot', 'pidfile'))
    else:
        pid_fn = '/var/run/elastic-recheck/elastic-recheck.pid'

    if args.foreground:
        _main(args, config)
    else:
        pid = pid_file_module.TimeoutPIDLockFile(pid_fn, 10)
        with daemon.DaemonContext(pidfile=pid):
            _main(args, config)


def setup_logging(config):
    """Turn down dependent library log levels so they aren't noise."""
    FORMAT = '%(asctime)s  %(levelname)-8s [%(name)-15s] %(message)s'
    DATEFMT = '%Y-%m-%d %H:%M:%S'
    # set 3rd party library logging levels to sanity points
    loglevels = {
        "irc.client": logging.INFO,
        "gerrit.GerritWatcher": logging.INFO,
        "paramiko.transport": logging.INFO,
        "pyelasticsearch": logging.INFO,
        "requests.packages.urllib3.connectionpool": logging.WARN
    }
    for module in loglevels:
        log = logging.getLogger(module)
        log.setLevel(loglevels[module])

    if config.has_option('ircbot', 'log_config'):
        log_config = config.get('ircbot', 'log_config')
        fp = os.path.expanduser(log_config)
        if not os.path.exists(fp):
            raise Exception("Unable to read logging config file at %s" % fp)
        logging.config.fileConfig(fp)
    else:
        logging.basicConfig(
            level=logging.DEBUG,
            format=FORMAT,
            datefmt=DATEFMT
        )


if __name__ == "__main__":
    main()
