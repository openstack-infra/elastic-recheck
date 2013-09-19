#! /usr/bin/env python

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


import ConfigParser
import daemon
import irc.bot
import os
import sys
import threading
import time
import yaml
import logging

from elasticRecheck import Stream
from elasticRecheck import Classifier

try:
    import daemon.pidlockfile
    pid_file_module = daemon.pidlockfile
except Exception:
    # as of python-daemon 1.6 it doesn't bundle pidlockfile anymore
    # instead it depends on lockfile-0.9.1
    import daemon.pidfile
    pid_file_module = daemon.pidfile


class RecheckWatchBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channels, nickname, password, server, port=6667,
                 server_password=None):
        irc.bot.SingleServerIRCBot.__init__(
            self, [(server, port, server_password)], nickname, nickname)
        self.channel_list = channels
        self.nickname = nickname
        self.password = password
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
        self.connection.privmsg(channel, msg)
        time.sleep(0.5)


class RecheckWatch(threading.Thread):
    def __init__(self, ircbot, channel_config, username, queries, host):
        threading.Thread.__init__(self)
        self.ircbot = ircbot
        self.channel_config = channel_config
        self.log = logging.getLogger('recheckwatchbot')
        self.username = username
        self.queries = queries
        self.host = host
        self.connected = False

    def new_error(self, channel, data):
        msg = '%s change: %s failed tempest with an unrecognized error' % (
            data['change']['project'],
            data['change']['url'])
        self.log.info('Compiled Message %s: %s' % (channel, msg))
        self.ircbot.send(channel, msg)

    def error_found(self, channel, data):
        msg = ('%s change: %s failed tempest because of: '
               'https://bugs.launchpad.net/bugs/%s' % (
            data['change']['project'],
            data['change']['url'],
            data['bug_number']))
        self.log.info('Compiled Message %s: %s' % (channel, msg))
        self.ircbot.send(channel, msg)

    def _read(self, data):
        for channel in self.channel_config.channels:
            if data.get('bug_number'):
                if channel in self.channel_config.events['positive']:
                    self.error_found(channel, data)
            else:
                if channel in self.channel_config.events['negative']:
                    self.new_error(channel, data)

    def run(self):
        classifier = Classifier(self.queries)
        stream = Stream(self.username, self.host)
        while True:
            event = stream.get_failed_tempest()
            change = event['change']['number']
            rev = event['patchSet']['number']
            change_id = "%s,%s" % (change, rev)
            project = event['change']['project']
            bug_number = classifier.classify(change, rev, event['comment'])
            if bug_number is None:
                self._read(event)
                stream.leave_comment(project, change_id)
            else:
                event['bug_number'] = bug_number
                self._read(event)
                stream.leave_comment(project, change_id, bug_number)


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


def _main():
    config = ConfigParser.ConfigParser({'server_password': None})
    config.read(sys.argv[1])
    setup_logging(config)

    fp = config.get('ircbot', 'channel_config')
    if fp:
        fp = os.path.expanduser(fp)
        if not os.path.exists(fp):
            raise Exception("Unable to read layout config file at %s" % fp)
    else:
        raise Exception("Channel Config must be specified in config file.")

    channel_config = ChannelConfig(yaml.load(open(fp)))

    bot = RecheckWatchBot(channel_config.channels,
                          config.get('ircbot', 'nick'),
                          config.get('ircbot', 'pass'),
                          config.get('ircbot', 'server'),
                          config.getint('ircbot', 'port'),
                          config.get('ircbot', 'server_password'))
    recheck = RecheckWatch(bot, channel_config,
                           config.get('gerrit', 'user'),
                           config.get('gerrit', 'query_file'),
                           config.get('gerrit', 'host', 'review.openstack.org'))

    recheck.start()
    bot.start()


def main():
    if len(sys.argv) != 2:
        print "Usage: %s CONFIGFILE" % sys.argv[0]
        sys.exit(1)

    pid = pid_file_module.TimeoutPIDLockFile(
        "/tmp/recheckwatchbot.pid", 10)
    with daemon.DaemonContext(pidfile=pid):
        _main()


def setup_logging(config):
    if config.has_option('ircbot', 'log_config'):
        log_config = config.get('ircbot', 'log_config')
        fp = os.path.expanduser(log_config)
        if not os.path.exists(fp):
            raise Exception("Unable to read logging config file at %s" % fp)
        logging.config.fileConfig(fp)
    else:
        logging.basicConfig(level=logging.DEBUG)


if __name__ == "__main__":
    main()
