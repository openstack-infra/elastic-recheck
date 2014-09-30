#!/usr/bin/env python

# Copyright 2013 OpenStack Foundation
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

"""Common logging for all ER efforts"""

import logging
import logging.config
import os

CONFIGURED = False


def setup_logging(config=None):
    """Turn down dependent library log levels so they aren't noise."""
    global CONFIGURED
    FORMAT = '%(asctime)s  %(levelname)-8s [%(name)-15s] %(message)s'
    DATEFMT = '%Y-%m-%d %H:%M:%S'
    # set 3rd party library logging levels to sanity points
    loglevels = {
        "irc.client": logging.INFO,
        "gerrit.GerritWatcher": logging.INFO,
        "paramiko.transport": logging.INFO,
        "pyelasticsearch": logging.INFO,
        "requests.packages.urllib3.connectionpool": logging.WARN,
        "urllib3.connectionpool": logging.WARN
    }

    if config is not None and config.has_option('ircbot', 'log_config'):
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
        for module in loglevels:
            log = logging.getLogger(module)
            log.setLevel(loglevels[module])
    CONFIGURED = True


def getLogger(name):
    global CONFIGURED
    if not CONFIGURED:
        setup_logging()
    return logging.getLogger(name)
