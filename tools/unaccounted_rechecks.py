#!/usr/bin/python
#
# Copyright 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import getpass
import os.path
import re
import time

from gerritlib import gerrit


def get_options():
    parser = argparse.ArgumentParser(
        description='Find rechecks not accounted for in ER')
    parser.add_argument('-u', '--user', help='Gerrit User',
                        default=getpass.getuser())
    tryfiles = ('id_gerrit', 'id_rsa', 'id_dsa')
    default_key = ""
    for f in tryfiles:
        trykey = os.path.join(os.path.expanduser("~"), '.ssh', f)
        if os.path.exists(trykey):
            default_key = trykey
            break
    parser.add_argument('-k', '--key', help='Gerrit SSH Key',
                        default=default_key)
    parser.add_argument('-d', '--dir', help="Queries Directory",
                        default="queries")
    parser.add_argument('-D', '--days', help="Number of Days to Query",
                        default=14)
    return parser.parse_args()


def connect_to_gerrit(user, key):
    return gerrit.Gerrit('review.openstack.org', user, 29418, key)


def collect_rechecks(gerrit, days="14"):
    # query only during the last 2 weeks, as that's what ER knows about
    since = int(time.time()) - 24 * 60 * 60 * int(days)
    changes = []
    sortkey = None
    while True:
        query = ("--patch-sets --comments project:^openstack.* "
                 " NOT age:%sd" % days)
        if sortkey:
            query += " resume_sortkey:%s" % sortkey

        data = gerrit.bulk_query(query)
        if len(data) <= 1:
            # means we only have the counter row
            break

        for d in data:
            if 'comments' in d:
                sortkey = d['sortKey']
                comments = d['comments']
                project = d['project']
                for comment in comments:
                    if comment['timestamp'] < since:
                        # bail early if the comment is outside the ER window
                        continue

                    m = re.search('recheck (no bug|bug (\#)?(?P<bugno>\d+))$',
                                  comment['message'])
                    if m:
                        dev = None
                        if 'username' in comment['reviewer']:
                            dev = comment['reviewer']['username']
                        bug = m.group('bugno') or 'no bug'
                        changes.append(
                            {'dev': dev,
                             'project': project,
                             'bug': bug,
                             'review': d['url']})
    return changes


def has_er_bug(dirname, bug):
    return os.path.exists(os.path.join(dirname, "%s.yaml" % bug))


def cross_ref_with_er(changes, dirname):
    for i in range(len(changes)):
        changes[i]['er'] = has_er_bug(dirname, changes[i]['bug'])
    return changes


def summarize_changes(changes):
    no_er = {}
    print("Summary")
    print("%4.4s - Total Rechecks" % (len(changes)))
    print("%4.4s - Total w/Bug" % (
        len([c for c in changes if c['bug'] != 'no bug'])))
    print("%4.4s - Total w/Bug and new recheck" % (
        len([c for c in changes if (c['bug'] != 'no bug' and not c['er'])])))

    for c in changes:
        bug = c['bug']
        if bug != 'no bug' and not c['er']:
            if bug not in no_er:
                no_er[bug] = {'count': 0, 'reviews': []}
            no_er[bug]['count'] += 1
            no_er[bug]['reviews'].append(c['review'])
    print()
    print("New bugs")
    for k, v in no_er.items():
        print("Bug %s found %d times" % (k, v['count']))
        for rev in v['reviews']:
            print("  - %s" % rev)


def main():
    opts = get_options()
    g = connect_to_gerrit(opts.user, opts.key)
    changes = collect_rechecks(g, opts.days)
    changes = cross_ref_with_er(changes, opts.dir)
    summarize_changes(changes)

if __name__ == "__main__":
    main()
