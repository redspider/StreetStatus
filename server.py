from datetime import datetime
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
        if not self.get_secure_cookie('street'):
            self.render("index.html")
            return

        street = self.get_secure_cookie('street')
        name = self.get_secure_cookie('name') or ''

        # Retrieve street details (pagination would be good)
        notices = mc.notices.find({'street': street}).sort([('dated',-1)]).limit(40)

        self.render("street.html", street=street, notices=notices, name=name, format_date=format_date)

    @tornado.web.asynchronous
    def post(self, *args, **kwargs):
        """ Switch streets """
        street = self.get_argument('street')
        # Verify street
        http = tornado.httpclient.AsyncHTTPClient()
        http.fetch("http://maps.googleapis.com/maps/api/geocode/json?address="+url_escape(street + ", Christchurch, New Zealand")+"&sensor=false", callback=self.on_response)

    def on_response(self, response):
        result = json_decode(response.body)
        log.debug(response.body)

        # Bad results?
        if result['status'] != 'OK':
            self.send_error(404,content="Got bad status for street")
            return

        # Build the canonical street name
        street_parts = []
        for component in result['results'][0]['address_components']:
            if 'route' in component['types']:
                street_parts.append(component['long_name'])

        if not len(street_parts):
            self.send_error(404,content="Couldn't find street components")
            return

        street = ', '.join(street_parts)

        # Set cookie
        self.set_secure_cookie('street',street)
        # Redirect
        self.redirect('/')

class LogoutHandler(tornado.web.RequestHandler):
    def post(self, *args, **kwargs):
        self.set_secure_cookie('street','', expires_days=-1)
        self.set_secure_cookie('name','', expires_days=-1)
        self.redirect('/')

class FindStreetHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self, *args, **kwargs):
        """ Switch streets """
        street = self.get_argument('street')
        # Verify street
        http = tornado.httpclient.AsyncHTTPClient()
        http.fetch("http://maps.googleapis.com/maps/api/geocode/json?address="+url_escape(street + ", Christchurch, New Zealand")+"&sensor=false", callback=self.on_response)

    def on_response(self, response):
        result = json_decode(response.body)
        log.debug(response.body)

        streets = []
        if result['status'] == 'OK':
            streets = [c['formatted_address'] for c in result['results'] if "route" in c['types']]
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

        name = self.get_argument('name')
        # Record name for auto-fill
        self.set_secure_cookie('name',name)

        notice = {
            'dated': bson.timestamp.Timestamp(datetime.now(),0),
            'name': name,
            'street': street,
        }

        if self.get_argument('type') == 'checkin':
            notice['type'] = 'checkin'
        else:
            notice['type'] = 'notice'
            notice['message'] = linkify(self.get_argument('message'))

        mc.notices.insert(notice)

        self.redirect('/')

#configure the Tornado application
application = tornado.web.Application(
    [(r"/", IndexHandler), (r"/post", PostHandler), (r"/find", FindStreetHandler), (r'/logout', LogoutHandler)],
    static_path = os.path.join(os.path.dirname(__file__), "static"),
    cookie_secret = "I can't believe it's not butter"
)

if __name__ == "__main__":
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8889)
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.start()