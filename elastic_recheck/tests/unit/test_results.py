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

import json

from elastic_recheck import results
from elastic_recheck import tests


def load_sample(bug):
    with open("elastic_recheck/tests/unit/samples/bug-%s.json" % bug) as f:
        return json.load(f)


class TestBasicParsing(tests.TestCase):

    def test_basic_parse(self):
        data = load_sample(1191960)
        result_set = results.ResultSet(data)
        self.assertEqual(len(result_set), 144)
        self.assertEqual(result_set.took, 45)

        hit1 = result_set[0]
        self.assertEqual(hit1.build_status, "SUCCESS")
        self.assertEqual(hit1.build_patchset, "3")
        self.assertEqual(hit1.project, "openstack/tempest")
        self.assertEqual(hit1.timestamp, "2013-10-18T17:39:43.966Z")

    def test_full_iteration(self):
        data = load_sample(1240256)
        result_set = results.ResultSet(data)
        self.assertEqual(len(result_set), 95)
        self.assertEqual(result_set.took, 78)

        for result in result_set:
            self.assertEqual(result.build_status, "FAILURE")
