# Copyright 2014 Samsung Electronics. All Rights Reserved.
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

import json


class GerritDone(Exception):
    pass


class Gerrit(object):
    """A fake gerrit libobject that emits a bunch of events."""
    def __init__(self, *args):
        with open("elastic_recheck/tests/unit/gerrit/events.json") as f:
            self.events = json.load(f)

    def startWatching(self):
        pass

    def getEvent(self):
        if len(self.events) > 0:
            return self.events.pop()
        else:
            raise GerritDone()
