#!/usr/bin/env python
#
# Copyright 2015 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
This is a simple test server that serves up the web content locally
as if it was a working remote server. It also proxies all the live
date/*.json files into the local test server, so that the Ajax async
loading works without hitting Cross Site Scripting violations.
"""

import argparse
import BaseHTTPServer
import os.path
import urllib2

SERVER_UPSTREAM = "http://status.openstack.org/elastic-recheck"


class ERHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """A request handler to create a magic local ER server"""

    def do_GET(self):
        # redirect to elastic recheck page
        if self.path == "/":
            self.path = "/index.html"

        # if the file exists locally, we'll serve it up directly
        fname = "web/share" + self.path
        if os.path.isfile(fname):
            print "found local file %s" % (fname)
            self.send_response(200, "Success")
            self.end_headers()
            with open(fname) as f:
                for line in f.readlines():
                    # in order for us to fetch the .json files, we
                    # need to have them served from our server,
                    # otherwise browser cross site scripting
                    # protections kick in. So rewrite content on the
                    # fly for those redirects.
                    line = line.replace(
                        "status.openstack.org/elastic-recheck",
                        "localhost:%s" % self.server.server_port)
                    self.wfile.write(line)
            return

        # If you've not built local data to test with, instead grab
        # the data off the production server on the fly and serve it
        # up from our server.
        if self.path.startswith("/data/"):
            try:
                response = urllib2.urlopen("%s%s" %
                                           (SERVER_UPSTREAM, self.path))
                self.send_response(200, "Success")
                self.end_headers()
                self.wfile.write(response.read())
            except urllib2.HTTPError as e:
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(e.read())
            return

        # Fall through for paths we don't understand
        print "Unknown path requested: %s" % self.path


def parse_opts():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-p', '--port',
                        help='port to bind to [default: 8001]',
                        type=int,
                        default=8001)
    return parser.parse_args()


def main():
    opts = parse_opts()
    server_address = ('', opts.port)
    httpd = BaseHTTPServer.HTTPServer(server_address, ERHandler)

    print "Test Server is running at http://localhost:%s" % opts.port
    print "Ctrl-C to exit"
    print

    while True:
        httpd.handle_request()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print "\n"
        print "Thanks for testing! Please come again."
