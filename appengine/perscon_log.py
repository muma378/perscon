# Copyright (c) 2010 Anil Madhavapeddy <anil@recoil.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from google.appengine.ext import db
from django import http
from django.utils import simplejson as json
import logging
import time

class LogLevel:
    info = 'info'
    debug = 'debug'
    error = 'error'

class LogEntry(db.Model):
    created = db.DateTimeProperty(auto_now_add=True)
    level = db.StringProperty(required=True)
    origin = db.StringProperty()
    entry = db.TextProperty()

    def todict(self):
        return {'created': time.mktime(self.created.timetuple()), 'level':self.level,
                'origin':self.origin, 'entry':self.entry }

def dolog(level="info", origin=None, entry=""):
    LogEntry(level=level, origin=origin, entry=entry).put()
    origin = origin or "unknown"
    e = "%s: %s" % (origin, entry)
    if level == "info":
      logging.info(e)
    elif level == "debug":
      logging.debug(e)
    elif level == "error":
      logging.error(e)

def ldebug(origin=None, entry=""):
    dolog(level="debug", origin=origin, entry=entry)

def linfo(origin=None, entry=""):
    dolog(level="info", origin=origin, entry=entry)

def crud(req):
    if req.method == 'POST':
        j = json.loads(req.raw_post_data)
        l = dolog(level=j.get('level','info'), origin=j.get('origin',''), entry=j['entry'])
        return http.HttpResponse("ok", mimetype="text/plain")
    elif req.method == 'GET':
        offset = int(req.GET.get('start', '0'))
        limit = int(req.GET.get('limit','20'))
        rq = LogEntry.all().order('-created')
        rc = rq.count(1000)
        rs = rq.fetch(limit, offset=offset)
        rsd = {'results': rc, 'rows': map(lambda x: x.todict(), rs)}
        return http.HttpResponse(json.dumps(rsd,indent=2), mimetype='text/plain')
    return http.HttpResponseServerError("not implemented")
