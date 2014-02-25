# Copyright Samsung Electronics 2013. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Loader for elastic search queries.

A set of utility methods to load queries for elastic recheck.
"""

import glob
import logging
import os.path
import yaml

LOG = logging.getLogger('recheckwatchbot')


def load(directory='queries'):
    """Load queries from a set of yaml files in a directory."""
    bugs = glob.glob("%s/*.yaml" % directory)
    data = []
    for fname in bugs:
        bugnum = os.path.basename(fname).rstrip('.yaml')
        query = yaml.load(open(fname).read())
        query['bug'] = bugnum
        data.append(query)
    return data
