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

"""Elastic search wrapper to make handling results easier."""

import pyelasticsearch


class SearchEngine(object):
    """Wrapper for pyelasticsearch so that it returns result sets."""
    def __init__(self, url):
        self._url = url

    def search(self, query, size=1000):
        """Search an elasticsearch server.

        `query` parameter is the complicated query structure that
        pyelasticsearch uses. More details in their documentation.

        `size` is the max number of results to return from the search
        engine. We default it to 1000 to ensure we don't loose things.
        For certain classes of queries (like faceted ones), this can actually
        be set very low, as it won't impact the facet counts.

        The returned result is a ResultSet query.
        """
        es = pyelasticsearch.ElasticSearch(self._url)
        results = es.search(query, size=size)
        return ResultSet(results)


class ResultSet(object):
    """An easy iterator object for handling elasticsearch results.

    pyelasticsearch returns very complex result structures, and manipulating
    them directly is both ugly and error prone. The point of this wrapper class
    is to give us a container that makes working with pyes results more
    natural.

    For instance:
         results = se.search(...)
         for hit in results:
              print hit.build_status

    This greatly simplifies code that is interacting with search results, and
    allows us to handle some schema instability with elasticsearch, through
    adapting our __getattr__ methods.

    Design goals for ResultSet are that it is an iterator, and that all the
    data that we want to work with is mapped to a flat attribute namespace
    (pyes goes way overboard with nesting, which is fine in the general
    case, but in the elastic_recheck case is just added complexity).
    """
    def __init__(self, results):
        self._results = results
        self._hits = self._parse_hits(results['hits'])

    def _parse_hits(self, hits):
        _hits = []
        # why, oh why elastic search
        hits = hits['hits']
        for hit in hits:
            _hits.append(Hit(hit))
        return _hits

    def __getattr__(self, attr):
        """Magic __getattr__, flattens the attributes namespace.

        First search to see if a facet attribute exists by this name,
        secondly look at the top level attributes to return.
        """
        if 'facets' in self._results:
            if attr in self._results['facets']['tag']:
                return self._results['facets']['tag'][attr]
        if attr in self._results:
            return self._results[attr]

    def __iter__(self):
        return iter(self._hits)

    def __getitem__(self, key):
        return self._hits[key]

    def __len__(self):
        return self._results['hits']['total']


class Hit(object):
    def __init__(self, hit):
        self._hit = hit

    def index(self):
        return self._hit['_index']

    def __getattr__(self, attr):
        """flatten out our attr space into a few key types

        new style ES has
          _source[attr] for a flat space
        old style ES has
          _source['@attr'] for things like @message, @timestamp
        and
         _source['@fields'][attr] for things like build_name, build_status

        also, always collapse down all attributes to singletons, because
        they might be lists if we use multiline processing (which we do
        a lot). In the general case this could be a problem, but the way
        we use logstash, there is only ever one element in these lists.
        """
        def first(item):
            if type(item) == list:
                return item[0]
            return item

        result = None
        at_attr = "@%s" % attr
        if attr in self._hit['_source']:
            result = first(self._hit['_source'][attr])
        elif at_attr in self._hit['_source']:
            result = first(self._hit['_source'][at_attr])
        elif attr in self._hit['_source']['@fields']:
            result = first(self._hit['_source']['@fields'][attr])

        return result

    def __str__(self):
        return "%s" % self._hit
