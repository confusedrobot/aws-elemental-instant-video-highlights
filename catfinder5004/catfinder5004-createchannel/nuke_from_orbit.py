#!/usr/bin/env python
import boto3
import json
import time
import uuid
import sys
from docopt import docopt
from pprint import pprint
import botocore

## LOOK Here!!! you will need to change this
REGION = 'eu-west-1'

session = boto3.Session(
    # profile_name='ibc'
    )

medialive = session.client(
    'medialive', 
    region_name=REGION, 
    )
mediapackage = session.client(
    'mediapackage', 
    region_name=REGION, 
    )

class Timeout(Exception):
     """Timeout exception"""
     pass
 
class _timeout:
    """Timeout handler"""
    def __init__(self, secs = None): self.secs = secs
    def __enter__(self):
        if self.secs is not None:
            signal.signal(signal.SIGALRM, self.handle)
            signal.alarm(self.secs)
    def handle(self, sig, frame): raise Timeout()
    def __exit__(self, type, val, traceback):
        if self.secs is not None: signal.alarm(0)

class _elapsed:
    """Measure elapsed time"""
    def __enter__(self):
        self.time0 = default_timer()
        return self
    def __exit__(self, type, value, trackback): pass
    def elapsed(self): return default_timer() - self.time0

def list_channels(timeout=None):
    token = ''
    channels = []
    with _timeout(timeout):
        while True:
            chan = medialive.list_channels(NextToken=token)
            token = chan.get('NextToken', '')
            channels.extend(chan['Channels'])
            if token == '': break
    for ch in channels:
        print('{} \t{} \t{}'.format(ch['Id'], ch['State'], ch['Name']))

def delete_all_the_channels(timeout=None):
    token = ''
    channels = []
    with _timeout(timeout):
        while True:
            chan = medialive.list_channels(NextToken=token)
            token = chan.get('NextToken', '')
            channels.extend(chan['Channels'])
            if token == '': break    
    pprint(channels)
    for ch in channels:
        print('stopping: {} \t{} \t{}'.format(ch['Id'], ch['State'], ch['Name']))
        if ch['State'] == 'IDLE':
            delete_and_wait_for_channel(ch['Id'])        
        if ch['State'] == 'RUNNING':
            final_state = stop_and_wait_for_channel(ch['Id'])
            if(final_state == 'IDLE'):
                delete_and_wait_for_channel(ch['Id'])
            else:
                print('Channel {} did not stop correctly :/ '.format(ch['Id']))

def delete_all_the_inputs(timeout=None):
    inputs = []
    token = ''
    with _timeout(timeout):
        while True:
            inp = medialive.list_inputs(NextToken=token)
            token = inp.get('NextToken', '')
            inputs.extend(inp['Inputs'])
            if token == '': break    
    pprint(inputs)
    for this_input in inputs:
        if this_input['State'] == 'DETACHED':
            print('Deleting input {}'.format(this_input['Id']))
            input_resp = medialive.delete_input(InputId=this_input['Id'])
        if this_input['State'] == 'ATTACHED':
            print('WARNING input {} is still attached!!'.format(this_input['Id']))

def check_inputs(timeout=None):
    inputs_count = 0
    inputs = []
    token = ''
    with _timeout(timeout):
        while True:
            inp = medialive.list_inputs(NextToken=token)
            token = inp.get('NextToken', '')
            inputs.extend(inp['Inputs'])
            if token == '': break    
    pprint(inputs)
    for this_input in inputs:
        inputs_count += 1
        print('WARNING: stubburn Input found! ')
    print('inputs_count: {}'.format(inputs_count))
    return inputs_count

def check_channels(timeout=None):
    channels_count = 0
    token = ''
    channels = []
    with _timeout(timeout):
        while True:
            chan = medialive.list_channels(NextToken=token)
            token = chan.get('NextToken', '')
            channels.extend(chan['Channels'])
            if token == '': break
    pprint(channels)
    for ch in channels:
        channels_count += 1
    print('channels_count: {}'.format(channels_count))        
    return channels_count

def check_mediapackage():
    channels_count = 0
    channels_to_clean = mediapackage.list_channels()        
        
    # clean channels after endpoints are obliterated
    for channel in channels_to_clean['Channels']:
        channels_count += 1
    print('package channels_count: {}'.format(channels_count))                
    return channels_count

def delete_all_the_mediapackage():
    channels_to_clean = mediapackage.list_channels()
    pprint(channels_to_clean)
    endpoints_to_clean = mediapackage.list_origin_endpoints()
    pprint(endpoints_to_clean)
    
    # need to clean up endpoints first
    for endpoint in endpoints_to_clean['OriginEndpoints']:
        endpoint_id = endpoint['Id']
        resp = mediapackage.delete_origin_endpoint(Id = endpoint_id)
        
    # clean channels after endpoints are obliterated
    for channel in channels_to_clean['Channels']:
        channel_id = channel['Id']
        resp = mediapackage.delete_channel(Id = channel_id)    



def describe_a_channel(channel_id):
    print('Describing channel {}'.format(channel_id))
    channel_resp = medialive.describe_channel(ChannelId=channel_id)
    print('Channel name: {} id: {} is in {} state'.format(channel_resp['Name'], channel_resp['Id'], channel_resp['State']))
    return channel_resp['State']

def describe_a_channel_details(channel_id):
    print('Describing channel {}'.format(channel_id))
    channel_resp = medialive.describe_channel(ChannelId=channel_id)
    print('Channel name: {} id: {} is in {} state'.format(channel_resp['Name'], channel_resp['Id'], channel_resp['ChannelState']))
    pprint(channel_resp['EncoderSettings']['VideoDescriptions'])

def stop_a_channel(channel_id):
    print('Stopping channel {}'.format(channel_id))
    channel_resp = medialive.stop_channel(ChannelId=channel_id)
    print('Channel Stopped: {}'.format(channel_resp))

def delete_a_channel(channel_id):
    print('Deleting channel {}'.format(channel_id))
    channel_resp = medialive.delete_channel(ChannelId=channel_id)
    print('Channel Deleted: {}'.format(channel_resp))

def delete_an_input(input_id):
    print('Deleting input {}'.format(input_id))
    input_resp = medialive.delete_input(InputId=input_id)
    print('Input Deleted: {}'.format(input_resp))

def delete_a_mediapackage_channel(channel_name):
    print('Deleting Mediapackage channel {}'.format(channel_name))
    # Delete Endpoints
    endpoint_count = 0
    endpoints_listing = mediapackage.list_origin_endpoints()
    for endpoint in endpoints_listing['OriginEndpoints']:
        resp = mediapackage.delete_origin_endpoint(Id = endpoint['Id'])
        print('enpoint-a deleted: {}'.format(resp))
        endpoint_count += 1
        resp = mediapackage.delete_origin_endpoint(Id = endpoint['Id'])
        print('enpoint-b deleted: {}'.format(resp))
        endpoint_count += 1            
    
    # Delete Channels
    channel_count = 0
    channels_listing = mediapackage.list_channels()
    for channel in channels_listing['Channels']:
        resp = mediapackage.delete_channel(Id = channel['Id'])    
        print('channel-p deleted: {}'.format(resp))
        channel_count += 1            
        resp = mediapackage.delete_channel(Id = channel['Id'])    
        print('channel-b deleted: {}'.format(resp))
        channel_count += 1            
    print('Mediapackage Channels Deleted: {} Endpoints Deleted: {}'.format(channel_count,endpoint_count))            
            

def wait_for_channel(channel_id, states, timeout_secs):
     """
     Waits for channel to reach one of the states
     """
     timeout_millis = timeout_secs * 1000
     start_time = time.time()
     current_state = describe_a_channel(channel_id)
     while current_state not in states:
         time.sleep(3)
         current_state = describe_a_channel(channel_id)
         now = time.time()
         if (now - start_time > timeout_secs):
             print('Channel did not reach desired state, giving up')
             break
     return current_state
 
def stop_and_wait_for_channel(channel_id):
    stop_a_channel(channel_id)
    final_state = wait_for_channel(channel_id, states=['IDLE'], timeout_secs=120)
    return final_state
 
def delete_and_wait_for_channel(channel_id):
    delete_a_channel(channel_id)
    # wait_for_no_channel(channel_id, timeout_secs=60)

if __name__ == '__main__':
    
    with _timeout(None):
        while True:
            all_count = 0            
            delete_all_the_channels()
            delete_all_the_mediapackage()
            delete_all_the_inputs()            
            all_count += check_inputs()
            all_count += check_channels()
            all_count += check_mediapackage()
            print('all_count: {}'.format(all_count))
            if all_count == 0: break      



 