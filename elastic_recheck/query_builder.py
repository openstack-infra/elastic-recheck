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

"""Query builder for pyelasticsearch

A set of utility methods to build the kinds of queries that are needed
by elastic recheck to talk with elastic search.
"""


def generic(raw_query, facet=None):
    """Base query builder

    Takes a raw_query string for elastic search. This is typically the same
    content that you've typed into logstash to get to a unique result.

    Optionally supports a facet, which is required for certain opperations,
    like ensuring that all the expected log files for a job have been
    uploaded.
    """

    # they pyelasticsearch inputs are incredibly structured dictionaries
    # so be it
    query = {
        "sort": {
            "@timestamp": {"order": "desc"}
            },
        "query": {
            "query_string": {
                "query": raw_query
                }
            }
        }
    # if we have a facet, the query gets expanded
    if facet:
        data = dict(field=facet, size=200)
        # yes, elasticsearch is odd, and the way to do multiple facets
        # is to specify the plural key value
        if type(facet) == list:
            data = dict(fields=facet, size=200)

        query['facets'] = {
            "tag": {
                "terms": data
                }
            }

    return query


def result_ready(review=None, patch=None, name=None, short_build_uuid=None):
    """A query to determine if we have a failure for a particular patch.

    This is looking for a particular FAILURE line in the console log, which
    lets us know that we've got results waiting that we need to process.
    """
    return generic('filename:"console.html" AND '
                   'message:"[SCP] Copying console log" '
                   'AND build_status:"FAILURE" '
                   'AND build_change:"%s" '
                   'AND build_patchset:"%s" '
                   'AND build_name:"%s"'
                   'AND build_uuid:%s*' %
                   (review, patch, name, short_build_uuid))


def files_ready(review, patch, name, short_build_uuid):
    """A facetted query to ensure all the required files exist.

    When changes are uploaded to elastic search there is a delay in
    getting all the required log fixes into the system. This query returns
    facets for the failure on the filename, which ensures that we've
    found all the files in the system.
    """
    return generic('build_status:"FAILURE" '
                   'AND build_change:"%s" '
                   'AND build_patchset:"%s"'
                   'AND build_name:"%s"'
                   'AND build_uuid:%s*' %
                   (review, patch, name, short_build_uuid),
                   facet='filename')


def single_patch(query, review, patch, short_build_uuid):
    """A query for a single patch (review + revision).

    This is used to narrow down a particular kind of failure found in a
    particular patch iteration.
    """
    return generic('%s '
                   'AND build_change:"%s" '
                   'AND build_patchset:"%s"'
                   'AND build_uuid:%s*' %
                   (query, review, patch, short_build_uuid))
