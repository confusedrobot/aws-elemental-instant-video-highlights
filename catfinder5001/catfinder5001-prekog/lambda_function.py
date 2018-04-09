from urllib2 import urlopen as wget
import datetime
import os
from pprint import pprint
import json
from decimal import Decimal
import boto3
import time
from boto3.dynamodb.conditions import Key, Attr
import urlparse
import hashlib
import urllib2
import xml.etree.ElementTree as ET
from botocore.exceptions import ClientError
import uuid
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

## These are unique and must be set
S3_BUCKET = "not-set"
EMP_URL = 'not-set'
CHANNEL_NAME = 'not-set'

XRAY = 'true'

## hardcoded for console use
DYNAMO_MAIN = "catfinder5000-main"
DYNAMO_MAIN_GSI = "id_type-id_filename-index"
DYNAMO_LIST = "catfinder5000-list"
DYNAMO_SUMMARY = "catfinder5000-summary"
LAMBDA_VOD = 'catfinder5001-vod'

dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
mediapackage = boto3.client('mediapackage')


def get_environment_variables():
    print('get_environment_variables')
    global EMP_URL 
    global DYNAMO_MAIN 
    global DYNAMO_MAIN_GSI 
    global DYNAMO_LIST 
    global DYNAMO_SUMMARY 
    global LAMBDA_VOD
    global CHANNEL_NAME
    global S3_BUCKET

    if os.environ.get('CHANNEL_NAME') is not None:
        CHANNEL_NAME = os.environ['CHANNEL_NAME']
        print('environment variable CHANNEL_NAME was found: {}'.format(CHANNEL_NAME))
        endpoints = mediapackage.list_origin_endpoints()
        for endpoint in endpoints['OriginEndpoints']:
            if endpoint['Id'] == CHANNEL_NAME:
                EMP_URL = endpoint['Url']
        print('environment variable EMP_URL was automagically set to: {}'.format(EMP_URL))
    if os.environ.get('EMP_URL') is not None:
        EMP_URL = os.environ['EMP_URL']
        print('environment variable EMP_URL was found: {}'.format(EMP_URL))
    if os.environ.get('S3_BUCKET') is not None:
        S3_BUCKET = os.environ['S3_BUCKET']
        print('environment variable S3_BUCKET was found: {}'.format(S3_BUCKET))
    if os.environ.get('DYNAMO_MAIN') is not None:
        DYNAMO_MAIN = os.environ['DYNAMO_MAIN']
        print('environment variable DYNAMO_MAIN was found: {}'.format(DYNAMO_MAIN))
    if os.environ.get('DYNAMO_MAIN_GSI') is not None:
        DYNAMO_MAIN_GSI = os.environ['DYNAMO_MAIN_GSI']
        print('environment variable DYNAMO_MAIN_GSI was found: {}'.format(DYNAMO_MAIN_GSI))
    if os.environ.get('DYNAMO_LIST') is not None:
        DYNAMO_LIST = os.environ['DYNAMO_LIST']
        print('environment variable DYNAMO_LIST was found: {}'.format(DYNAMO_LIST))
    if os.environ.get('DYNAMO_SUMMARY') is not None:
        DYNAMO_SUMMARY = os.environ['DYNAMO_SUMMARY']
        print('environment variable DYNAMO_SUMMARY was found: {}'.format(DYNAMO_SUMMARY))
    if os.environ.get('LAMBDA_VOD') is not None:
        LAMBDA_VOD = os.environ['LAMBDA_VOD']
        print('environment variable LAMBDA_VOD was found: {}'.format(LAMBDA_VOD))


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        return super(DecimalEncoder, self).default(o)


def put_dynamo(query_dict):
    print("put_dynamo to table: " + str(DYNAMO_LIST))
    table = dynamodb.Table(DYNAMO_LIST)
    this_uuid = str(uuid.uuid4())
    label_sort = str(int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds())) + this_uuid
    try:
        response = table.put_item(
            Item={
                    'entry_id': this_uuid,
                    'timestamp_created': int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds()),
                    'timestamp_ttl': int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + 900 ),
                    'label': query_dict['label'],
                    'time_start': query_dict['time_start'],
                    'time_start_frame': query_dict['time_start_frame'],
                    'time_start_image': query_dict['time_start_image'],
                    'time_end': query_dict['time_end'],
                    'time_end_frame': query_dict['time_end_frame'],
                    'time_end_image': query_dict['time_end_image'], 
                    'label_image': query_dict['label_image'], 
                    'messages_backward': query_dict['messages_backward'], 
                    'messages_forward': query_dict['messages_forward'], 
                    'hops_backward': query_dict['hops_backward'], 
                    'hops_forward': query_dict['hops_forward'], 
                    'emp_url':  query_dict['emp_url'], 
                    'label_sort': label_sort,
            },
            ConditionExpression='attribute_not_exists(entry_id)'
        )
        print("dynamo put_item succeeded: {}".format(response))
    except ClientError as e:
        # Ignore the ConditionalCheckFailedException, bubble up other exceptions.
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise
    return {
        's3_bucket' : S3_BUCKET,
        'entry_id': this_uuid,
        'label': query_dict['label'],
        'time_start': query_dict['time_start'],
        'time_start_frame': query_dict['time_start_frame'],
        'time_start_image': query_dict['time_start_image'],
        'time_end': query_dict['time_end'],
        'time_end_frame': query_dict['time_end_frame'],
        'time_end_image': query_dict['time_end_image'], 
        'label_image': query_dict['label_image'], 
        'messages_backward': query_dict['messages_backward'], 
        'messages_forward': query_dict['messages_forward'], 
        'hops_backward': query_dict['hops_backward'], 
        'hops_forward': query_dict['hops_forward'], 
        'emp_url':  query_dict['emp_url'], 
        'label_sort': label_sort,
    }

def get_hops(rekog_label, id_filename, scan_index):
    table = dynamodb.Table(DYNAMO_MAIN)    
    exclusive_start_key = { 'id_type' : 'scenechange', 'id_filename': id_filename}
    response = table.query(
        IndexName=DYNAMO_MAIN_GSI,
        Limit=  1,
        ScanIndexForward=scan_index,
        ExclusiveStartKey=exclusive_start_key,
        KeyConditionExpression=Key('id_type').eq('scenechange'),
    )
    return response
def detect_hops(rekog_label, id_filename, scan_index):
    scenechange_threshold = 10
    prekog_continue = 1
    prekog_infinteloop = 0
    last_id_filename = id_filename
    all_hops = {}
    messages = []
    last_hop = {}
    loop_count = 0
    while prekog_continue > 0:
        loop_count += 1
        prekog_continue = 0
        response = get_hops(rekog_label, last_id_filename, scan_index)
        if len(response['Items']) < 1:
            print('LOOP: items has less than 1: {} we are too fast lets sleep'.format(len(response['Items'])))
            messages.append('LOOP: items has less than 1: we are too fast lets sleep')
            prekog_continue += 1
            time.sleep(4)
        else:
            for this_item in response['Items']:
                # pprint(this_item)
                last_hop = this_item
                if last_id_filename == this_item['id_filename']:
                    print('END: we got the same id_filename {} == {} BREAK!'.format(last_id_filename, this_item['id_filename']))
                    messages.append('END: we got the same id_filename {} == {} BREAK!'.format(last_id_filename, this_item['id_filename']))
                    break
                else:
                     last_id_filename = this_item['id_filename']   
                for this_label in this_item['rekog_labels']:
                    if this_label['Name'] == rekog_label:
                        print('LOOP: matched rekog_label: {} must go deeper \t{}:{};{}'.format(rekog_label, this_item['timestamp_minute'],this_item['timestamp_second'],this_item['timestamp_frame']))
                        messages.append('LOOP: matched rekog_label: {} must go deeper {}:{};{}'.format(rekog_label, this_item['timestamp_minute'],this_item['timestamp_second'],this_item['timestamp_frame']))
                        prekog_continue += 1
                if int(this_item['scenedetect']) < scenechange_threshold:
                    print('LOOP: scenedetect is too low {} must go deeper \t{}:{};{}'.format(int(this_item['scenedetect']), this_item['timestamp_minute'],this_item['timestamp_second'],this_item['timestamp_frame'] ))
                    messages.append('LOOP: scenedetect is too low {} must go deeper {}:{};{}'.format(int(this_item['scenedetect']), this_item['timestamp_minute'],this_item['timestamp_second'],this_item['timestamp_frame'] ))
                    prekog_continue += 1 
                else:
                    print('END: scenedetect is high enough {} \t{}:{};{}'.format(int(this_item['scenedetect']), this_item['timestamp_minute'],this_item['timestamp_second'],this_item['timestamp_frame'] ))
                    messages.append('END: scenedetect is high enough {} {}:{};{}'.format(int(this_item['scenedetect']), this_item['timestamp_minute'],this_item['timestamp_second'],this_item['timestamp_frame'] ))
                all_hops[str(loop_count)] = this_item
        prekog_infinteloop += 1
        if prekog_infinteloop > 15: 
            print('END: infinteloop detected BREAK!')
            messages.append('END: infinteloop detected BREAK!')
            break
        else:
            print('LOOP: infinteloop count: {}'.format(prekog_infinteloop))
            messages.append('LOOP: infinteloop count: {}'.format(prekog_infinteloop))
    # pprint(last_hop)
    print('INFO: prekog_continue completed loop count: {}'.format(loop_count))
    messages.append('INFO: prekog_continue completed loop count: {}'.format(loop_count))
    payload = {
        'last_hop': last_hop,
        'messages': messages,
        'all_hops': all_hops,
    }
    return(payload)

def invoke_lambda(dynamo_object):
    invoke_response = lambda_client.invoke(FunctionName=LAMBDA_VOD,  InvocationType='Event', Payload=json.dumps(dynamo_object, cls=DecimalEncoder))
    print("invoke: {}".format(dynamo_object))
    print("invoke " + str(LAMBDA_VOD) + " code: " + str(invoke_response['StatusCode']))


def lambda_handler(event, context):
    if XRAY == 'true':
        patch_all()
    get_environment_variables()  
    print('event: {}'.format(event))
    print('S3_BUCKET: {}'.format(S3_BUCKET))
    print('EMP_URL: {}'.format(EMP_URL))
    if EMP_URL == 'not-set':
        return 'ERROR: EMP_URL was not set'
    rekog_label = event['rekog_label']
    id_filename = event['id_filename']
    print('rekog_label: {} \tid_filename: {}'.format(rekog_label, id_filename))

    ## BACKWARDS in time
    if int(event['scenedetect']) > 50:
        print('first scene is {}, skipping hops_backwards'.format(event['scenedetect']))
        hops_backward = {
            'last_hop': event,
            'messages': ['first scene is {}, skipping hops_backwards'.format(event['scenedetect'])],
            'all_hops': { '1': event },
        }
    else:
        hops_backward = detect_hops(rekog_label, id_filename, False)
    print('hops_backward: {}'.format(hops_backward))

    ## FORWARD in time ( may have to wait for time to actually happen )
    hops_forward = detect_hops(rekog_label, id_filename, True)
    print('hops_forward: {}'.format(hops_forward))

    query_dict = {}
    query_dict['label_image'] = id_filename
    query_dict['label'] = rekog_label

    query_dict['time_start'] = hops_backward['last_hop']['timestamp_minute']+ ':' + hops_backward['last_hop']['timestamp_second']
    query_dict['time_start_frame'] = str(hops_backward['last_hop']['timestamp_frame'])
    query_dict['time_start_image'] = hops_backward['last_hop']['id_filename']
    query_dict['messages_backward'] = hops_backward['messages']
    query_dict['hops_backward'] = hops_backward['all_hops']

    query_dict['time_end'] = hops_forward['last_hop']['timestamp_minute']+ ':' + hops_forward['last_hop']['timestamp_second']
    query_dict['time_end_frame'] = str(hops_forward['last_hop']['timestamp_frame'])
    query_dict['time_end_image'] = hops_forward['last_hop']['id_filename']
    query_dict['messages_forward'] = hops_forward['messages']
    query_dict['hops_forward'] = hops_forward['all_hops']
    # pprint(query_dict)

    query_dict['emp_url'] = EMP_URL + '?start=' + query_dict['time_start'].replace(' ','T') + '+00:00&end=' + query_dict['time_end'].replace(' ','T') + '+00:00'
    lambda_event = put_dynamo(query_dict)
    pprint(lambda_event)
    invoke_lambda(lambda_event)
    return 'SUCCESS: it ran'


if __name__ == "__main__":
    XRAY = 'false'
    # os.environ['EMP_URL'] = 'https://c4af3793bf76b33c.mediapackage.us-west-2.amazonaws.com/out/v1/1ed8596038884d739eb8f5b9556b00ec/index.m3u8'
    os.environ['CHANNEL_NAME'] = 'catfinder5001___'
    os.environ['LAMBDA_VOD'] = 'catfinder5001-vod'
    os.environ['DYNAMO_MAIN'] = "catfinder5000-main"
    # os.environ['DYNAMO_MAIN_GSI'] = "id_type-id_filename-index" ## should be fine to hardcode
    os.environ['S3_BUCKET'] = 'catfinder5000-demo'
    get_environment_variables()      
    print("getting sample data from table: " + str(DYNAMO_MAIN))
    table = dynamodb.Table(DYNAMO_MAIN)
    response = table.query(
        IndexName=DYNAMO_MAIN_GSI,
        Limit=  15,
        ScanIndexForward=False,
        KeyConditionExpression=Key('id_type').eq('scenechange'),
    )
    print(response['Items'][3]['rekog_labels'][1]['Name'])
    event = response['Items'][3]
    # event = {
    #     'id_filename' : str(response['Items'][6]['id_filename']),
    #     'scenedetect' : str(response['Items'][6]['scenedetect']),
    #     # 'id_filename' : 'channel1_540p20171017T050350_69328-26.jpg',
    #     'rekog_label' : str(response['Items'][6]['rekog_labels'][1]['Name'])
    #     # 'rekog_label' : 'Blonde'
    # }
    event['rekog_label'] = str(response['Items'][3]['rekog_labels'][1]['Name'])
    # pprint(event)
    print(lambda_handler(event,None))
    # write scripts for deploy and logs
    with open('deploy', 'w') as outfile:
        outfile.write('lambda-uploader --variables \'{"CHANNEL_NAME": "' + CHANNEL_NAME + '","LAMBDA_VOD": "' + LAMBDA_VOD + '","DYNAMO_MAIN": "' + DYNAMO_MAIN + '","S3_BUCKET": "' + S3_BUCKET + '" }\'')
    with open('logs', 'w') as outfile:
        outfile.write('awslogs get /aws/lambda/catfinder5001-prekog ALL --watch')
