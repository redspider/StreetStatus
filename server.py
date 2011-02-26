from datetime import datetime
from time import time
import tornado.web
import tornado.websocket
import tornado.ioloop
import tornado.httpserver
import tornado.httpclient
from tornado.escape import linkify, url_escape, json_decode
import pymongo
import bson
import os
import logging
from upoints.point import Point

log = logging.getLogger()

logging.getLogger().setLevel(logging.DEBUG)

mongo_connection = pymongo.Connection()
mc = mongo_connection['street_status']

mc.notices.ensure_index([('dated',pymongo.DESCENDING)])
mc.notices.ensure_index([('street',pymongo.DESCENDING)])

def format_date(t):
    d = t.as_datetime()
    return d.strftime('%d %b %H:%M')

class IndexHandler(tornado.web.RequestHandler):
    """Regular HTTP handler to serve the dashboard page"""
    def get(self, *args, **kwargs):
        """ Display street """
        name = self.get_secure_cookie('name') or ''


        if not self.get_secure_cookie('street'):
            self.render("index.html", name=name)
            return

        street = self.get_secure_cookie('street')

        # Retrieve street details (pagination would be good)
        notices = mc.notices.find({'street': street}).sort([('dated',-1)]).limit(40)
        geo = mc.streets.find_one({'street': street}) or 'none'

        self.render("street.html", street=street, notices=notices, name=name, format_date=format_date, geo=str(geo))

class LogoutHandler(tornado.web.RequestHandler):
    def post(self, *args, **kwargs):
        self.set_secure_cookie('street','', expires_days=-1)
        self.redirect('/')

class FindStreetHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self, *args, **kwargs):
        """ Switch streets """
        street = self.get_argument('street')

        name = self.get_argument('name')
        self.set_secure_cookie('name',name)
        log.debug("Setting name %s street %s" % (name, street))

        # Verify street
        http = tornado.httpclient.AsyncHTTPClient()
        http.fetch("http://maps.googleapis.com/maps/api/geocode/json?address="+url_escape(street + ", Christchurch, New Zealand")+"&sensor=false", callback=self.on_response)



    def on_response(self, response):
        result = json_decode(response.body)
        log.debug(response.body)

        streets = []
        if result['status'] == 'OK':
            streets = [c['formatted_address'] for c in result['results'] if "route" in c['types']]

            for c in result['results']:
                mc.streets.insert({'street': c['formatted_address'], 'geo': c})

        if len(streets) == 1:
            self.set_secure_cookie('street', streets[0])
            self.redirect('/')

        self.render("select_street.html", streets=streets)

    def get(self, *args, **kwargs):
        # Set cookie
        self.set_secure_cookie('street',self.get_argument('street'))
        # Redirect
        self.redirect('/')


class PostHandler(tornado.web.RequestHandler):
    """ Post a notice """
    def post(self, *args, **kwargs):
        """ New notice """
        street = self.get_secure_cookie('street')
        if not street:
            self.send_error(403)

        notice = {
            'dated': bson.timestamp.Timestamp(datetime.now(),0),
            'name': self.get_secure_cookie('name'),
            'street': street,
        }

        if self.get_argument('type') == 'checkin':
            notice['type'] = 'checkin'
        else:
            notice['type'] = self.get_argument('type')
            notice['message'] = linkify(self.get_argument('message'))

        mc.notices.insert(notice)

        self.redirect('/')

incidents = []
incident_map = {}

def rebuild_location_cache():
    global incidents,incident_map
    incidents = []
    incident_map = {}
    for incident in mc.incident.find({}):
        point = Point(incident['latitude'],incident['longitude'])
        incidents.append((incident['id'], point))
        incident_map[incident['id']] = incident

    tornado.ioloop.IOLoop.instance().add_timeout(time.time()+60, rebuild_location_cache)
    
    
#configure the Tornado application
application = tornado.web.Application(
    [(r"/", IndexHandler), (r"/post", PostHandler), (r"/find", FindStreetHandler), (r'/logout', LogoutHandler)],
    static_path = os.path.join(os.path.dirname(__file__), "static"),
    cookie_secret = "I can't believe it's not butter"
)

if __name__ == "__main__":
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8889)

    # Build location cache
    rebuild_location_cache()
    
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.start()