# Copyright Samsung Electronics 2013. All Rights Reserved.
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

import calendar
import copy
import datetime
import pprint

import dateutil.parser as dp
import pyelasticsearch
import pytz


pp = pprint.PrettyPrinter()


class SearchEngine(object):
    """Wrapper for pyelasticsearch so that it returns result sets."""
    def __init__(self, url):
        self._url = url

    def search(self, query, size=1000, recent=False):
        """Search an elasticsearch server.

        `query` parameter is the complicated query structure that
        pyelasticsearch uses. More details in their documentation.

        `size` is the max number of results to return from the search
        engine. We default it to 1000 to ensure we don't loose things.
        For certain classes of queries (like faceted ones), this can actually
        be set very low, as it won't impact the facet counts.

        `recent` search only most recent indexe(s), assuming this is basically
        a real time query that you only care about the last hour of time.
        Using recent dramatically reduces the load on the ES cluster.

        The returned result is a ResultSet query.

        """
        es = pyelasticsearch.ElasticSearch(self._url)
        args = {'size': size}
        if recent:
            # today's index
            datefmt = 'logstash-%Y.%m.%d'
            now = datetime.datetime.utcnow()
            lasthr = now - datetime.timedelta(hours=1)
            indexes = [now.strftime(datefmt)]
            if (lasthr.strftime(datefmt) != now.strftime(datefmt)):
                indexes.append(lasthr.strftime(datefmt))
            args['index'] = indexes

        results = es.search(query, **args)
        return ResultSet(results)


class ResultSet(list):
    """An easy iterator object for handling elasticsearch results.

    pyelasticsearch returns very complex result structures, and manipulating
    them directly is both ugly and error prone. The point of this wrapper class
    is to give us a container that makes working with pyes results more
    natural.

    For instance:

    ::

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
    def __init__(self, results={}):
        self._results = results
        if 'hits' in results:
            self._parse_hits(results['hits'])

    def _parse_hits(self, hits):
        # why, oh why elastic search
        hits = hits['hits']
        for hit in hits:
            list.append(self, Hit(hit))

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


class FacetSet(dict):
    """A dictionary like collection for creating faceted ResultSets.

    Elastic Search doesn't support nested facets, which are incredibly
    useful for things like faceting by build_status then by build_uuid.
    This is a client side implementation that processes a ResultSet
    with an ordered list of facets, and turns it into a data structure
    which is FacetSet -> FacetSet ... -> ResultSet (arbitrary nesting
    of FaceSets with ResultSet as the leaves.

    Treat this basically like a dictionary (which it inherits from).
    """
    def _histogram(self, data, facet, res=3600):
        """A preprocessor for data should we want to bucket it."""
        if facet == "timestamp":
            ts = dp.parse(data)
            tsepoch = int(calendar.timegm(ts.timetuple()))
            # take the floor based on resolution
            ts -= datetime.timedelta(
                seconds=(tsepoch % res),
                microseconds=ts.microsecond)
            # ms since epoch
            epoch = datetime.datetime.fromtimestamp(0, pytz.UTC)
            pos = int(((ts - epoch).total_seconds()) * 1000)
            return pos
        else:
            return data

    def detect_facets(self, results, facets, res=3600):
        if len(facets) > 0:
            facet = facets.pop(0)
            for hit in results:
                attr = self._histogram(hit[facet], facet)
                if attr not in self:
                    dict.setdefault(self, attr, ResultSet())
                    self[attr].append(hit)
                else:
                    self[attr].append(hit)

            # if we still have more facets to go, recurse down
            if len(facets) > 0:
                newkeys = {}
                for key in self:
                    fs = FacetSet()
                    fs.detect_facets(self[key], copy.deepcopy(facets), res=res)
                    newkeys[key] = fs
                self.update(newkeys)


class Hit(object):
    def __init__(self, hit):
        self._hit = hit

    def index(self):
        return self._hit['_index']

    def __getitem__(self, key):
        return self.__getattr__(key)

    def __getattr__(self, attr):
        """flatten out our attr space into a few key types

        new style ES has
          _source[attr] for a flat space
        old style ES has
          _source['@attr'] for things like message, @timestamp
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

    def __repr__(self):
        return pp.pformat(self._hit)
