#!env python
"""
Pull report data from Ushahidi
"""
import datetime
import time

#import os, sys, random, logging
import logging
import pymongo
#import bson
from optparse import OptionParser
import urllib, urllib2
import simplejson

mongo_connection = pymongo.Connection()
mc = mongo_connection['street_status']

logging.basicConfig(level=logging.WARN)
log = logging.getLogger()

def time_to_datetime(t):
    return datetime.datetime.fromtimestamp(time.mktime(time.strptime(t,"%Y-%m-%d %H:%M:%S")))

def ush_pull(url, limit):
    """ Open URL, grab data, feed to mongodb """

    # Obtain minimum current ID
    minimum_id = 0
    high_row = list(mc.incident.find({},['id']).sort([('id',-1)]).limit(1))
    if len(high_row) > 0:
        minimum_id = high_row[0]['id']

    print minimum_id

    raw_result = urllib2.urlopen(url+"/api?"+urllib.urlencode({'task': 'incidents','by': 'all','resp': 'json', 'limit': str(limit)})).read()
    result = simplejson.loads(raw_result)
    for row in result['payload']['incidents']:
        document = {
            'id': int(row['incident']['incidentid']),
            'categories': [{'id': int(c['category']['id']), 'title': c['category']['title']} for c in row['categories']],
            'title': row['incident']['incidenttitle'],
            'description': row['incident']['incidentdescription'],
            'dated': time_to_datetime(row['incident']['incidentdate']),
            'location': {
                'name': row['incident']['locationname'],
                'latitude': float(row['incident']['locationlatitude']),
                'longitude': float(row['incident']['locationlongitude'])
            }
        }

        if document['id'] > minimum_id:
            print "Inserting %d %s" % (document['id'], document['title'])
            mc.incident.insert(document)

    print "Done"

if __name__ == "__main__":
    usage = "usage: %prog [options] [filename]"
    parser = OptionParser(usage="usage: %prog [options] filename")
    parser.add_option("--verbose","-v",
                      help = "print debugging output",
                      action = "store_true")
    parser.add_option("--url","-u",
                      help = "Ushahidi URL",
                      type = "string",
                      default = "http://eq.org.nz/",
                      action = "store")
    parser.add_option("--limit","-l",
                      help = "Import limit",
                      type="int",
                      default=10000,
                      action="store")

    (options, args) = parser.parse_args()
    if options.verbose:
        log.setLevel(logging.DEBUG)

    log.debug("Verbose mode: %s" % options.verbose)
    log.debug("URL: %s" % options.url)

    ush_pull(options.url, options.limit)