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
import os.path
import yaml


def load(directory='queries'):
    """Load queries from a set of yaml files in a directory."""
    bugs = glob.glob("%s/*.yaml" % directory)
    data = []
    for fname in bugs:
        bugnum = os.path.basename(fname).rstrip('.yaml')
        query = yaml.load(open(fname).read())
        query['bug'] = bugnum
        # By default we filter out non-voting jobs, but in certain cases we
        # want to show failures for non-voting jobs in the graph while we
        # stabilize a job, so check for a special 'allow-nonvoting' key.
        if not query.get('allow-nonvoting', False):
            query['query'] = "%s AND voting:1" % query['query'].rstrip()
        data.append(query)
    return data
