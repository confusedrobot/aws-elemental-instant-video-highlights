# -*- coding: utf-8 -*-

import urllib2
import json
import xml.etree.ElementTree as ET
from pprint import pprint as vardump
from time import gmtime, strftime, sleep
import time
import hashlib
import datetime
import urlparse
import boto3
from collections import defaultdict
import datetime

apikey = "IOiW89n8iZHtjzBtq6o"
user = "leahtradeshow"


def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k:v[0] if len(v) == 1 else v for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v) for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
              d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d

def report_error( error_message ):
    print error_message

def elemental_api(my_urlinput, methods='GET', payload='', datatype='xml'):
    vardump(my_urlinput)
    datatype_str = 'application/xml'
    if datatype == 'xml':
        datatype_str = 'application/xml'
    if datatype == 'json':
        datatype_str = 'application/json'
    futuretime2 = 2
    currenttime = time.time()
    finaltime = int(currenttime + futuretime2 * 60)
    parsed = urlparse.urlparse(my_urlinput)
    url = parsed.path
    print(url, datatype_str, methods, datatype)
    ###creating the REST API hash information
    prehash = "%s%s%s%s" % (url,user,apikey,finaltime)
    mdinner = hashlib.md5(prehash).hexdigest()
    prehash2 = "%s%s" % (apikey,mdinner)
    finalhash =  hashlib.md5( prehash2 ).hexdigest()
    req = urllib2.Request(my_urlinput)
    req.add_header("Content-type", datatype_str)
    req.add_header("Accept", datatype_str)
    req.add_header("X-Auth-User", user)
    req.add_header("X-Auth-Expires", finaltime)
    req.add_header("X-Auth-Key", finalhash)
    if methods == "POST":
        req.get_method = lambda: 'POST'
    if methods == "GET":
        req.get_method = lambda: 'GET'
    if methods == "PUT":
        req.get_method = lambda: 'PUT'
    if methods == "DELETE":
        req.get_method = lambda: 'DELETE'
    response_xml = urllib2.urlopen(url=req, data=payload).read()
    return(response_xml)
    
def live_event(url, id):
    this_url = url + '/live_events/' + id + '/inputs'
    callback_str = elemental_api(this_url)
    vardump(callback_str)    

def live_activateinput(url, id, activate_time, input_label):
    this_url = url + '/live_events/' + id + '/activate_input'
    xml = '<activate_input><input_label>' + input_label + '</input_label><utc_time>' + activate_time + '</utc_time></activate_input>'
    vardump(xml)
    # xml = '<input_id>' + input_label + '</input_id> <utc_time>' + activate_time + '</utc_time>'
    # xml = '<input_label>' + input_label + '</input_label> '
    callback_str = elemental_api(this_url, 'POST', xml)
    vardump(callback_str)



def lambda_handler(event, context):
    live_hostname = 'https://rkwgwprkuw4a1.cloud.elementaltechnologies.com'
    time_now = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S.%f") #YYYYMMDDThhmmss.
    vardump(time_now)
    time_next = (datetime.timedelta(seconds=10) + datetime.datetime.utcnow()).strftime("%Y%m%dT%H%M%S.000")
    vardump(time_next)
    live_activateinput(live_hostname, '11', time_next, 'start' )
    live_activateinput(live_hostname, '10', time_next, 'start' )
    live_activateinput(live_hostname, '8', time_next, 'start' )
    live_activateinput(live_hostname, '7', time_next, 'start' )
    live_activateinput(live_hostname, '6', time_next, 'start' )
    live_activateinput(live_hostname, '5', time_next, 'start' )
    time_next_next = (datetime.timedelta(seconds=20) + datetime.datetime.utcnow()).strftime("%Y%m%dT%H%M%S.000")
    vardump(time_next_next)
    live_activateinput(live_hostname, '11', time_next_next, 'loop' )
    live_activateinput(live_hostname, '10', time_next_next, 'loop' )
    live_activateinput(live_hostname, '8', time_next_next, 'loop' )
    live_activateinput(live_hostname, '7', time_next_next, 'loop' )
    live_activateinput(live_hostname, '6', time_next_next, 'loop' )
    live_activateinput(live_hostname, '5', time_next_next, 'loop' )

    
print(lambda_handler(None,None))