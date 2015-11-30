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
import os

DEFAULT_INDEX_FORMAT = 'logstash-%Y.%m.%d'

ES_URL = 'http://logstash.openstack.org:80/elasticsearch'
LS_URL = 'http://logstash.openstack.org'
DB_URI = 'mysql+pymysql://query:query@logstash.openstack.org/subunit2sql'

JOBS_RE = '(tempest-dsvm-full|gate-tempest-dsvm-virtual-ironic)'
CI_USERNAME = 'jenkins'

PID_FN = '/var/run/elastic-recheck/elastic-recheck.pid'


class Config(object):

    def __init__(self,
                 config_file=None,
                 config_obj=None,
                 es_url=None,
                 ls_url=None,
                 db_uri=None,
                 jobs_re=None,
                 ci_username=None,
                 pid_fn=None,
                 es_index_format=None):

        self.es_url = es_url or ES_URL
        self.ls_url = ls_url or LS_URL
        self.db_uri = db_uri or DB_URI
        self.jobs_re = jobs_re or JOBS_RE
        self.ci_username = ci_username or CI_USERNAME
        self.es_index_format = es_index_format or DEFAULT_INDEX_FORMAT
        self.pid_fn = pid_fn or PID_FN
        self.ircbot_channel_config = None
        self.irc_log_config = None

        if config_file or config_obj:
            if config_obj:
                config = config_obj
            else:
                config = ConfigParser.ConfigParser(
                    {'es_url': ES_URL,
                     'ls_url': LS_URL,
                     'db_uri': DB_URI,
                     'server_password': None,
                     'ci_username': CI_USERNAME,
                     'jobs_regex': JOBS_RE,
                     'pidfile': PID_FN,
                     'index_format': DEFAULT_INDEX_FORMAT,
                     }
                )
                config.read(config_file)

            if config.has_section('data_source'):
                self.es_url = config.get('data_source', 'es_url')
                self.ls_url = config.get('data_source', 'ls_url')
                self.db_uri = config.get('data_source', 'db_uri')
                self.es_index_format = config.get('data_source',
                                                  'index_format')

            if config.has_section('recheckwatch'):
                self.ci_username = config.get('recheckwatch', 'ci_username')
                self.jobs_regex = config.get('recheckwatch', 'jobs_regex')

            if config.has_section('gerrit'):
                self.gerrit_user = config.get('gerrit', 'user')
                self.gerrit_query_file = config.get('gerrit', 'query_file')
                self.gerrit_host = config.get('gerrit', 'host',
                                              'review.openstack.org')
                self.gerrit_host_key = config.get('gerrit', 'key')

            if config.has_section('ircbot'):
                self.pid_fn = os.path.expanduser(config.get('ircbot',
                                                            'pidfile'))
                self.ircbot_nick = config.get('ircbot', 'nick')
                self.ircbot_pass = config.get('ircbot', 'pass')
                self.ircbot_server = config.get('ircbot', 'server')
                self.ircbot_port = config.getint('ircbot', 'port')
                self.ircbot_server_password = config.get('ircbot',
                                                         'server_password')
                self.ircbot_channel_config = config.get('ircbot',
                                                        'channel_config')
            if config.has_option('ircbot', 'log_config'):
                self.irc_log_config = config.get('ircbot', 'log_config')
