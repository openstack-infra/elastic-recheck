#!/usr/bin/env python

import ConfigParser
import sys

import gerritlib

def is_failed_tempest(event):
    if event.get('type', '') != 'comment-added':
        return False
    if event['author']['username'] == 'Jenkins':
        return True


def main():
    config = ConfigParser.ConfigParser()
    config.read('elasticRecheck.conf')
    host = 'review.openstack.org'
    user = config.get('gerrit', 'user', 'jogo')
    port = 29418
    import gerritlib.gerrit
    gerrit = gerritlib.gerrit.Gerrit(host, user, port)
    gerrit.startWatching()
    while True:
        event = gerrit.getEvent()
        if is_failed_tempest(event):
            print event['comment']


if __name__ == "__main__":
    main()
