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
from google.appengine.ext.db import NotSavedError

from django.utils import simplejson as json
import time, string, datetime
import logging
log = logging.info

def Key_to_uid(key):
    return key.name()

class DictProperty(db.Property):
    data_type = dict

    def get_value_for_datastore(self, model_instance):
      value = super(DictProperty, self).get_value_for_datastore(model_instance)
      return db.Text(json.dumps(value))

    def make_value_from_datastore(self, value):
      if value is None:
        return dict()
      return json.loads(value)

    def default_value(self):
      if self.default is None:
        return dict()
      else:
        return super(DictProperty, self).default_value().copy()

    def validate(self, value):
      if not isinstance(value, dict):
        raise db.BadValueError('Property %s needs to be convertible to a dict instance (%s) of class dict' % (self.name, value))
      return super(DictProperty, self).validate(value)

    def empty(self, value):
      return value is None

class Location(db.Model):
    loc = db.GeoPtProperty(required=True)
    date = db.DateTimeProperty(required=True)
    accuracy = db.FloatProperty()
    woeid = db.StringProperty()
    url = db.URLProperty()
    speed = db.FloatProperty()

    created = db.DateTimeProperty(auto_now_add=True)
    modified = db.DateTimeProperty(auto_now=True)

    def todict (self):
      return { 'lat': self.loc.lat, 'lon': self.loc.lon, 
               'date': time.mktime(self.date.timetuple()), 'woeid': self.woeid }

    # query the best location fit for this date/time
    @staticmethod
    def nearest_location_at_time(date):
        # just pick nearest one until we have a quadtree store
        q = Location.gql("WHERE date < :1 ORDER BY date DESC LIMIT 1", date)
        return q.get()

class Att(db.Model):
    mime = db.StringProperty(default="application/octet-stream")
    body = db.BlobProperty()

    def todict(self):
        return {'key': self.key().name(), 'mimetype': self.mime }

class Person(db.Model):
    first_name = db.StringProperty()
    last_name  = db.StringProperty()
    origin = db.StringProperty()
    created = db.DateTimeProperty()
    modified = db.DateTimeProperty(auto_now=True)
    services = db.ListProperty(db.Key)
    atts = db.ListProperty(db.Key)
    
    def todict(self):
      return { 'uid': self.key().name(), 'first_name': self.first_name, 
         'last_name': self.last_name, 'modified': time.mktime(self.modified.timetuple()), 
         'atts': map(lambda x: Att.get(x).todict(), self.atts),
         'services': map(lambda x: Service.get(x).todict(), self.services) }

    def tojson(self):
      return json.dumps(self.todict(), indent=2)

    @staticmethod
    def from_service(svc):
        q = Person.gql("WHERE services = :1 LIMIT 1", svc)
        res = q.fetch(1)
        if len(res) == 0:
            return None
        else:
            return res[0]

    @staticmethod
    def find_or_create(key):
        q = Person.get_by_key_name(key)
        if not q:
            q = Person(key_name=key)
        return q
 
class Service(db.Expando):
    ty = db.StringProperty(required=True)
    context = db.StringProperty()
    person = db.ReferenceProperty(Person)

    def todict(self, withPerson=False):
        if self.ty == 'im':
            v = [ self.value.protocol, self.value.address ]
        else:
            v = self.value
        if withPerson:
            person = self.person
            if person: person = person.todict()
            return {'ty':self.ty, 'context':self.context, 'value': v, 'person': person }
        else:
            return {'ty':self.ty, 'context':self.context, 'value': v}

    @staticmethod
    def ofdict(d,create=True):
        ty = d['ty']
        if ty == 'im': 
            v = db.IM(d['value'][0], address=d['value'][1])
        elif ty == 'email':
            v = db.Email(Service.normalize_email(d['value']))
        elif ty == 'url':
            v = d['value']
        elif ty == 'phone':
            v = db.PhoneNumber(Service.normalize_phone(d['value']))
        elif ty == 'postal':
            v = db.PostalAddress(d['value'])
        else:
            v = d['value']
        if create:
            return Service.find_or_create(ty, v)
        else:
            return Service.gql('WHERE ty=:1 AND value=:2 LIMIT 1', ty, v).get()
  
    @staticmethod
    def key_ofdict(d):
        d = Service.ofdict(d)
        try:
            d.key()
        except NotSavedError:
            d.put()
        return d.key()

    @staticmethod
    def ofjson(j):
        return Service.ofdict(simplejson.loads(j))

    @staticmethod
    def normalize_email(e):
        return e.lower()

    @staticmethod
    def normalize_phone(p):
        # XXX only works with UK numbers at the moment -avsm
        import re
        if len(p) < 1: return p
        pn = re.sub('[^0-9|\+]','',p)
        if len(pn) < 1: return pn
        if pn[0:1] == "00" and len(pn) > 2:
            pn = "+%s" % pn[2:]
        elif pn[0]  == '0':
            pn = "+44%s" % pn[1:]
        return pn

    @staticmethod
    def find_or_create(ty, v, key_name=None):
        q = Service.gql('WHERE ty=:1 AND value=:2 LIMIT 1', ty, v).get()
        if not q:
            if key_name:
                q = Service(key_name=key_name, ty=ty, value=v)
            else:
                q = Service(ty=ty,value=v)
        # XXX also need to check for dup services here if one exists already
        # or just implement multiple UIDs -avsm
        return q
 
    
class Message(db.Model):
    origin = db.StringProperty(required=True)
    frm = db.ListProperty(db.Key)
    to  = db.ListProperty(db.Key)
    atts = db.ListProperty(db.Key)
    created = db.DateTimeProperty(required=True)
    meta = DictProperty()
    modified = db.DateTimeProperty(auto_now=True)
    thread = db.StringProperty()
    thread_count = 0

    def todict(self):
      loc = Location.nearest_location_at_time(self.created)
      return { 'origin': self.origin,
               'frm': map(lambda x: Service.get(x).todict(withPerson=True), self.frm),
               'to': map(lambda x: Service.get(x).todict(withPerson=True), self.to),
               'atts' : map(lambda x: Att.get(x).todict(), self.atts),
               'uid' : self.key().name(),
               'modified': time.mktime(self.modified.timetuple()),
               'created': time.mktime(self.created.timetuple()),
               'loc': loc and loc.todict(),
               'thread': self.thread,
               'thread_count': self.thread_count
             }
           
    def tojson(self):
      return json.dumps(self.todict(), indent=2)

class SYNC_STATUS:
    unsynchronized = 'UNSYNCHRONIZED'
    inprogress = 'INPROGRESS'
    synchronized = 'SYNCHRONIZED'

def datetime_as_float(dt):
    '''Convert a datetime.datetime into a microsecond-precision float.'''
    return time.mktime(dt.timetuple())+(dt.microsecond/1e6)

class Sync(db.Model):
    service = db.StringProperty(required=True)
    username = db.StringProperty()
    status = db.StringProperty(required=True, default=SYNC_STATUS.unsynchronized)
    last_sync = db.DateTimeProperty()

    def todict(self):
      return { 'service': self.service,
               'username': self.username,
               'status': self.status,
               'last_sync': datetime_as_float(self.last_sync) if self.last_sync else None,
               }
    def tojson(self):
      return json.dumps(self.todict(), indent=2)

    @staticmethod
    def of_service(service, username):
        s = Sync.all().filter('service =', service).filter('username =', username).get()
        if not s:
            s = Sync(service=service, username=username, status=SYNC_STATUS.unsynchronized)
            s.put()
        return s

    def put(self):
        if self.status == SYNC_STATUS.synchronized:
            s = db.GqlQuery("SELECT * FROM Sync WHERE service=:s AND username=:u",
                        s=self.service, u=self.username).get()
            if (not s or (s and s.status != self.status)):
                self.last_sync = datetime.datetime.now()
        super(Sync, self).put()
