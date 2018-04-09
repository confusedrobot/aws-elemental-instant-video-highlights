from urllib2 import urlopen as wget
import urllib2
import urllib
import datetime
import os
import stat
from pprint import pprint
import json
from decimal import Decimal
import boto3
import time
from threading import Thread
import botocore
from botocore.client import ClientError
from boto3.dynamodb.conditions import Key, Attr
import uuid
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
import sys
import re

# patch_all()
XRAY = 'true'

## these are unique and must be set
S3_BUCKET = "not-set"
HLS_URL = 'not-set'
HLS_URL_PLAYLIST = 'not-set'
CHANNEL_NAME = 'not-set'

## hardcoded for console use
# DYNAMO_MAIN = "catfinder5004-main"
DYNAMO_MAIN_GSI = "id_type-id_filename-index"
# DYNAMO_LIST = "catfinder5004-list"
DYNAMO_SUMMARY_GSI = 'rekog_type-timestamp_updated-index'
SINGULAR_ENABLE = 'true'

FFPROBE = './ffprobe'
FFMPEG = './ffmpeg'

s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb')
rekognition = boto3.client("rekognition")
# lambda_client = boto3.client('lambda')


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

def get_environment_variables():
    global S3_BUCKET
    global HLS_URL
    global HLS_URL_PLAYLIST
    global DYNAMO_MAIN
    global DYNAMO_LIST

    if os.environ.get('S3_BUCKET') is not None:
        S3_BUCKET = os.environ['S3_BUCKET']
        print('environment variable S3_BUCKET was found: {}'.format(S3_BUCKET))
    if os.environ.get('DYNAMO_MAIN') is not None:
        DYNAMO_MAIN = os.environ['DYNAMO_MAIN']
        print('environment variable DYNAMO_MAIN was found: {}'.format(DYNAMO_MAIN))
    if os.environ.get('DYNAMO_LIST') is not None:
        DYNAMO_LIST = os.environ['DYNAMO_LIST']
        print('environment variable DYNAMO_LIST was found: {}'.format(DYNAMO_LIST))
    if os.environ.get('HLS_URL') is not None:
        HLS_URL = os.environ['HLS_URL']
        print('environment variable HLS_URL was found: {}'.format(HLS_URL))
    if os.environ.get('HLS_URL_PLAYLIST') is not None:
        HLS_URL_PLAYLIST = os.environ['HLS_URL_PLAYLIST']
        print('environment variable HLS_URL_PLAYLIST was found: {}'.format(HLS_URL_PLAYLIST))
    if os.environ.get('REKOG_LABEL') is not None:
        REKOG_LABEL = os.environ['REKOG_LABEL']
        print('environment variable REKOG_LABEL was found: {}'.format(REKOG_LABEL))

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        return super(DecimalEncoder, self).default(o)

def get_url(url, time = 20):
    try:
        output = wget(url, timeout = time).read()
    except urllib2.HTTPError, e:
        print(e.code)
        error_message = e.code
        print(error_message )
    except urllib2.URLError, e:
        print(e.args)
        error_message = e.args
        print( error_message )
    else:
        return output

def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

def save_file(name, data):
    f = open(name, 'w+')
    f.write(data)
    f.close()

def delete_file(myfile):
    if os.path.isfile(myfile):
        os.remove(myfile)
        # print("Success: %s file was deleted" % myfile)
    else:    ## Show an error ##
        print("Error: %s file not found" % myfile)

def get_s3file(BUCKET_NAME, KEY, LOCALFILE):
    try:
        s3.Bucket(BUCKET_NAME).download_file(KEY, LOCALFILE)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist. 404")
        else:
            raise

def put_dynamo_main(dynamo_object):
    print("put_dynamo to table: " + str(DYNAMO_MAIN))
    table = dynamodb.Table(DYNAMO_MAIN)
    try:
        response = table.put_item(
            Item=dynamo_object,
            ConditionExpression='attribute_not_exists(id_filename)'
        )
        # print("dynamo put_item succeeded: {}".format(response))
    except Exception as e:
        # Ignore the ConditionalCheckFailedException, bubble up other exceptions.
        print("ERROR: dynamo BORKED: {}".format(e)) 
        print('broken dynamo: {}'.format(dynamo_object))
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise e
        sys.exc_clear()


def write_json():

    ## set tmp directory
    tmpdir = '/tmp/' + str(uuid.uuid4()) + '/'
    ensure_dir(tmpdir)

    print("query of table: " + str(DYNAMO_LIST))
    table = dynamodb.Table(DYNAMO_LIST)    
    response = table.query(
        Limit=15,
        ScanIndexForward=False,
        KeyConditionExpression=Key('label').eq('scoreboard'),
    )
    json_string = json.dumps(response['Items'], cls=DecimalEncoder)
    dynamo_filename = 'list-vod.json'
    with open(tmpdir + dynamo_filename, 'w') as outfile:
        outfile.write(json_string)

    ## S3 upload
    data = open(tmpdir + dynamo_filename, 'rb')
    print(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))
    delete_file(tmpdir + dynamo_filename)

def get_scoreboard(tmpdir, filename_base, frames_total):
    scoreboard = {
        'score_left' : 'not-set',
        'score_right' : 'not-set',
        'shots_left' : 'not-set',
        'shots_right' : 'not-set',
        'game_clock' : 'not-set',
        'game_period' : 'not-set'
    }
    retry = 6
    retry_count = 0
    x_filename = 0
    ## Cycle through all frames
    for x in xrange(0, frames_total):  
        x_filename += 1
        # print('x_filename: {} retry: {}'.format(x_filename,retry))
        dynamo_filename = filename_base + '-' + str(x_filename).zfill(3) + '.jpg'        
        if retry > 0:  
            if x_filename==1:
                ## S3 upload
                data = open(tmpdir + dynamo_filename, 'rb')
                print(s3.Bucket(S3_BUCKET).put_object(Key='images/' + dynamo_filename, Body=data))
                # print(tmpdir + dynamo_filename)
                # delete_file(tmpdir + dynamo_filename)
                rekog_text = rekognition.detect_text(Image={"S3Object": {"Bucket": S3_BUCKET, "Name": 'images/' + dynamo_filename}})
                # pprint(rekog_text['TextDetections'])
                
                for item in rekog_text['TextDetections']:
                    if item['Type'] == 'WORD':
                        # print('{} is {}'.format(item['DetectedText'], item['Geometry']['BoundingBox']['Left']))
                        ## SCORE LEFT
                        if 0.12 <= float(item['Geometry']['BoundingBox']['Left']) <= 0.14:
                            # print('{} is Score Left'.format(item['DetectedText']))
                            if bool(re.search('^[0-4]$', item['DetectedText'].replace('O','0'))):
                                scoreboard['score_left'] = item['DetectedText'].replace('O','0')
                            else:
                                print('{} is GARBAGE'.format(item['DetectedText']))

                        ## SCORE RIGHT
                        if 0.74 <= float(item['Geometry']['BoundingBox']['Left']) <= 0.76:
                            # print('{} is Score Right'.format(item['DetectedText']))
                            if bool(re.search('^[0-4]$', item['DetectedText'].replace('O','0'))):
                                scoreboard['score_right'] = item['DetectedText'].replace('O','0')
                            else:
                                print('{} is GARBAGE'.format(item['DetectedText']))
                                
                            
                        ## GAME CLOCK
                        if 0.29 <= float(item['Geometry']['BoundingBox']['Left']) <= 0.37:
                            # print('{} is Game Clock'.format(item['DetectedText']))
                            match = re.search('([0-9]{1,2}:[0-9][0-9])|([0-9]{1,2})\.[0-9]', item['DetectedText'].replace('O','0'))
                            if bool(match) and match.group(1):
                                scoreboard['game_clock'] = match.group(1)
                                # print('matched group 1')
                            if bool(match) and match.group(2):
                                scoreboard['game_clock'] = str('0:') + match.group(2)
                                # print('matched group 2')

                                
                            
                        ## SHOTS LEFT
                        if 0.19 <= float(item['Geometry']['BoundingBox']['Left']) <= 0.24:
                            # print('{} is Shots Left'.format(item['DetectedText']))
                            match = re.search('([0-9]{1,2})', item['DetectedText'].replace('O','0'))
                            if bool(match):
                                scoreboard['shots_left'] = match.group(1)
                                # print('{} MATCHED Shots Left'.format(scoreboard['shots_left']))
                            else:
                                print('{} is GARBAGE'.format(item['DetectedText']))
                                
                            
                        ## SHOTS RIGHT
                        if 0.83 <= float(item['Geometry']['BoundingBox']['Left']) <= 0.86:
                            # print('{} is Shots Right'.format(item['DetectedText']))
                            if bool(re.search('^[0-9]{1,2}$', item['DetectedText'].replace('O','0'))):                
                                scoreboard['shots_right'] = item['DetectedText'].replace('O','0')
                            else:
                                print('{} is GARBAGE'.format(item['DetectedText']))
                                
                            
                        ## GAME PERIOD
                        if 0.58 <= float(item['Geometry']['BoundingBox']['Left']) <= 0.63:
                            # print('{} is Game Period'.format(item['DetectedText']))
                            if bool(re.search('^[0-3]$', item['DetectedText'].replace('O','0'))):                
                                scoreboard['game_period'] = item['DetectedText'].replace('O','0')
                            else:
                                print('{} is GARBAGE'.format(item['DetectedText']))
                                
                # print(scoreboard)
                retry = 0
                # for key, value in scoreboard.iteritems():
                #     print('{} {}'.format(key,value))
                #     if value == 'not-set':
                #         retry += 1
        # print('deleting: {}'.format(tmpdir + dynamo_filename))
        delete_file(tmpdir + dynamo_filename)

    return scoreboard

def get_segment_images(segment_datetime, segment_duration, segment_framerate, tmpdir, segment_filename, base_url):
    # get date time string without decimal 
    datetime_full = segment_datetime.split('.')[0] + 'Z'
    # print('datetime_full: {}'.format(datetime_full))

    # get datetime object from date time string without decimal
    datetime_datetime = datetime.datetime.strptime(datetime_full, "%Y-%m-%dT%H:%M:%SZ")
    # print('datetime_datetime: {}'.format(datetime_datetime))

    # get epoch of datetime
    epoch = datetime.datetime(1970,1,1)
    datetime_epoch = (datetime_datetime - epoch).total_seconds()
    # print('datetime_epoch: {}'.format(datetime_epoch))

    # get the decimal from the date time string 
    datetime_decimal = segment_datetime.split('.')[1].split('Z')[:-1]
    # print('datetime_decimal: {}'.format(datetime_decimal[0]))

    # convert decimal to frame number 
    datetime_frame = int(round(int(datetime_decimal[0]) * segment_framerate / 1000, 3))
    # print('datetime_frame: {}'.format(datetime_frame))

    # how many frames per segment 
    frames_total = int(round(float(segment_duration) * segment_framerate, 3))
    # print('frames_total: {}'.format(frames_total))

    # get filenames assumption started
    filename_base = segment_filename.split('.ts')[0]
    # print('filename_base: {}'.format(filename_base))

    # get the physical segment file
    get_s3file(S3_BUCKET, base_url + segment_filename, tmpdir + segment_filename)
    
    ## FFMPEG - generate a jpg for each frame
    output_ffmpeg = os.popen(FFMPEG + ' -hide_banner -nostats -loglevel error -y -i ' + tmpdir + segment_filename + ' -an -sn -vcodec mjpeg -pix_fmt yuvj420p -qscale 1 -b:v 2000 -bt 20M -filter "crop=240:50:340:300,scale=1280:-1" "' + tmpdir + filename_base + '-%03d.jpg"  > /dev/null 2>&1 ').read()
    # delete ts segment
    myfile = tmpdir + segment_filename
    delete_file(myfile)
    # print("file located: " + tmpdir + filename_base)
    # os.popen('open ' + tmpdir + filename_base + '.jpg')
    newest_scoreboard = get_scoreboard(tmpdir, filename_base, frames_total)
    return newest_scoreboard

def put_dynamo_list(dynamo_object, shot_object, scoreboard, image_filename, segment_datetime, trigger_type):
    print("put_dynamo to table: " + str(DYNAMO_LIST))
    table = dynamodb.Table(DYNAMO_LIST)
    this_uuid = str(uuid.uuid4())
    label_sort = str(int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds())) + this_uuid
    datetime_start = datetime.datetime.strptime(segment_datetime, '%Y-%m-%dT%H:%M:%S.%fZ')
    action_time = 15
    if trigger_type == 'score': 
        action_time = 25
    try:
        response = table.put_item(
            Item={
                    'entry_id': this_uuid,
                    'timestamp_created': int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds()),
                    'timestamp_ttl': int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + 900 ),
                    'label': 'scoreboard',
                    'end_time' : datetime_start.strftime("%Y-%m-%d %H:%M:%S").replace(' ', 'T') + '+00:00',
                    'start_time' : (datetime_start - datetime.timedelta(seconds=float(action_time))).strftime("%Y-%m-%d %H:%M:%S").replace(' ', 'T') + '+00:00',
                    'label_image': image_filename, 
                    'scoreboard': scoreboard, 
                    'shot_object': shot_object, 
                    'dynamo_object': dynamo_object, 
                    'trigger_type': trigger_type,
                    'label_sort': label_sort,
            },
            ConditionExpression='attribute_not_exists(entry_id)'
        )
        print("dynamo put_item succeeded: {}".format(response))
    except ClientError as e:
        # Ignore the ConditionalCheckFailedException, bubble up other exceptions.
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise

segment_duration = 1
prev_segment_duration = 1
def lambda_handler(event, context):
    # if XRAY == 'true':
        # patch_all()    
    get_environment_variables()  
    print('S3_BUCKET: {}'.format(S3_BUCKET))
    print('HLS_URL: {}'.format(HLS_URL))
    print('HLS_URL_PLAYLIST: {}'.format(HLS_URL_PLAYLIST))
    master_ttl = 3600
    if(HLS_URL_PLAYLIST != urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))):
        return 'wrong manifest'
    s3_version = event['Records'][0]['s3']['object']['versionId']
    # PARSE manifest
    print("master manifest: " + HLS_URL)
    
    # wrangle the urls
    base_url = 'live/'
    # print("baseurl: {}".format(base_url))
    filename_master = HLS_URL.split('/')[-1]
    # print("filename_master: {}".format(filename_master))

    ## set tmp directory
    tmpdir = '/tmp/' + str(uuid.uuid4()) + '/'
    ensure_dir(tmpdir)

    # GET master manifest
    get_s3file(S3_BUCKET, HLS_URL, tmpdir + filename_master)
    string_master = open(tmpdir + filename_master, 'r').read()
    # print("string_master: {}".format(string_master))

    # PARSE frame rate for the segments
    segment_framerate = float(string_master.split('FRAME-RATE=')[1].split(',')[0].split('\n')[0])
    print("segment_framerate: {}".format(segment_framerate))

    ## Note: this is not needed, but could use it as a checksum 
    # PARSE the m3u8 child manifestss. Returns list of these strings
    # filename_playlists = [x for x in string_master.split('\n') if '.m3u8' in x]
    # print("filename_playlists: {}".format(filename_playlists))
    
    filename_playlist = HLS_URL_PLAYLIST.split('/')[-1]
    # print("filename_playlist: {}".format(filename_playlist))

    # GET child manifest
    # get_s3file(S3_BUCKET, HLS_URL_PLAYLIST, tmpdir + filename_playlist)
    try:
        s3.Bucket(S3_BUCKET).download_file(HLS_URL_PLAYLIST, tmpdir + filename_playlist, ExtraArgs={'VersionId': s3_version})
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist. 404")
        else:
            raise

    string_playlist = open(tmpdir + filename_playlist, 'r').read()
    # print("string_playlist: {}".format(string_playlist))

    # PARSE list of DATE-time and segment name and get last one
    segment_datetime = ''
    segment_duration = ''
    segment_filename = ''
    prev_segment_datetime = ''
    prev_segment_duration = ''
    prev_segment_filename = ''
    
    for x in string_playlist.split('#EXT-X-PROGRAM-DATE-TIME:'):
        if '.ts' in x:
            prev_segment_datetime = segment_datetime
            prev_segment_duration = segment_duration
            prev_segment_filename = segment_filename
            segment_datetime = x.split('\n#EXTINF')[0]
            segment_duration = x.split('#EXTINF:')[1].split(',\n')[0]
            segment_filename = x.split('#EXTINF:')[1].split(',\n')[1].split('\n')[0]
    # print('segment_datetime: {}'.format(segment_datetime))
    # print('segment_duration: {}'.format(segment_duration))
    # print('segment_filename: {}'.format(segment_filename))
    # print('prev_segment_datetime: {}'.format(prev_segment_datetime))
    # print('prev_segment_duration: {}'.format(prev_segment_duration))
    # print('prev_segment_filename: {}'.format(prev_segment_filename))

    newest_scoreboard = get_segment_images(segment_datetime, segment_duration, segment_framerate, tmpdir, segment_filename, base_url)
    # previous_scoreboard = get_segment_images(prev_segment_datetime, prev_segment_duration, segment_framerate, tmpdir, prev_segment_filename, base_url)
    print("newest_scoreboard: {}".format(newest_scoreboard))
    # print(previous_scoreboard)

    table = dynamodb.Table(DYNAMO_MAIN)    
    response = table.query(
        IndexName=DYNAMO_MAIN_GSI,
        Limit=  1,
        ScanIndexForward=False,
        KeyConditionExpression=Key('id_type').eq('scoreboard'),
    )
    # print(response['Items'])
    if len(response['Items']) > 0:
        if newest_scoreboard['score_left'] == 'not-set':
            if response['Items'][0]['score_left'] != 'not-set':
                print('from newest entry score_left from: {} to {}'.format(newest_scoreboard['score_left'],response['Items'][0]['score_left']))
                newest_scoreboard['score_left'] = response['Items'][0]['score_left']

        if newest_scoreboard['shots_left'] == 'not-set':
            if response['Items'][0]['shots_left'] != 'not-set':
                print('from newest entry shots_left from: {} to {}'.format(newest_scoreboard['shots_left'],response['Items'][0]['shots_left']))
                newest_scoreboard['shots_left'] = response['Items'][0]['shots_left']

        if newest_scoreboard['score_right'] == 'not-set':
            if response['Items'][0]['score_right'] != 'not-set':
                print('from newest entry score_right from: {} to {}'.format(newest_scoreboard['score_right'],response['Items'][0]['score_right']))
                newest_scoreboard['score_right'] = response['Items'][0]['score_right']

        if newest_scoreboard['shots_right'] == 'not-set':
            if response['Items'][0]['shots_right'] != 'not-set':
                print('from newest entry shots_right from: {} to {}'.format(newest_scoreboard['shots_right'],response['Items'][0]['shots_right']))
                newest_scoreboard['shots_right'] = response['Items'][0]['shots_right']

        if newest_scoreboard['game_clock'] == 'not-set':
            if response['Items'][0]['game_clock'] != 'not-set':
                print('from newest entry game_clock from: {} to {}'.format(newest_scoreboard['game_clock'],response['Items'][0]['game_clock']))
                newest_scoreboard['game_clock'] = response['Items'][0]['game_clock']

        if newest_scoreboard['game_period'] == 'not-set':
            if response['Items'][0]['game_period'] != 'not-set':
                print('from newest entry game_period from: {} to {}'.format(newest_scoreboard['game_period'],response['Items'][0]['game_period']))
                newest_scoreboard['game_period'] = response['Items'][0]['game_period']
    else:
        print("WARNING: no dynamoDB entries")

    dynamo_object = {}
    dynamo_object={
            'id_filename': segment_filename,
            'id_type': 'scoreboard',
            'segment_datetime': segment_datetime,
            'score_left': newest_scoreboard['score_left'],
            'shots_left': newest_scoreboard['shots_left'],
            'score_right': newest_scoreboard['score_right'],
            'shots_right': newest_scoreboard['shots_right'],
            'game_clock': newest_scoreboard['game_clock'],
            'game_period': newest_scoreboard['game_period'],
            # 'scoreboard_json': scoreboard,
            'timestamp_created' : int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds()),
            'timestamp_ttl' : int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + master_ttl) # 2 hours
    }

    put_dynamo_main(dynamo_object)

    table = dynamodb.Table(DYNAMO_MAIN)    
    exclusive_start_key = { 'id_type' : 'scoreboard', 'id_filename': segment_filename}
    response = table.query(
        IndexName=DYNAMO_MAIN_GSI,
        Limit=  1,
        ScanIndexForward=False,
        ExclusiveStartKey=exclusive_start_key,
        KeyConditionExpression=Key('id_type').eq('scoreboard'),
    )
    # print(response)
    scored_object = {
        "element_id": "ebf6d47f-56c3-4550-92df-32ccd10dca8a", 
        "ts": segment_datetime,
        "payload": {
            "Team 1 Goal" : 'false',
            "Team 2 Goal" : 'false'
        }
    }
    shot_object = {
        "element_id": "ebf6d47f-56c3-4550-92df-32ccd10dca8a", 
        "ts": segment_datetime,
        "payload": {
            "Team 1 Shot" : 'false',
            "Team 2 Shot" : 'false'
        }
    }    
    period_object = {
        "element_id": "ebf6d47f-56c3-4550-92df-32ccd10dca8a", 
        "ts": segment_datetime,
        "payload": {
            "period" : '0',
        }
    }     
    teams_scored = 'false'
    teams_shot = 'false'
    period_change = 'false'
    if len(response['Items']) > 0:
        if newest_scoreboard['score_left'] == 'not-set':
            if response['Items'][0]['score_left'] != 'not-set':
                print('reverting score_left from: {} to {}'.format(newest_scoreboard['score_left'],response['Items'][0]['score_left']))
                newest_scoreboard['score_left'] = response['Items'][0]['score_left']
        else:
            if response['Items'][0]['score_left'] != 'not-set':
                if int(newest_scoreboard['score_left']) > int(response['Items'][0]['score_left']):
                    print('SCORE team1: {} from {}'.format(newest_scoreboard['score_left'],response['Items'][0]['score_left']))
                    scored_object["payload"]['Team 1 Goal'] = 'true'
                    teams_scored = 'true'

        if newest_scoreboard['shots_left'] == 'not-set':
            if response['Items'][0]['shots_left'] != 'not-set':
                print('reverting shots_left from: {} to {}'.format(newest_scoreboard['shots_left'],response['Items'][0]['shots_left']))
                newest_scoreboard['shots_left'] = response['Items'][0]['shots_left']
        else:
            if response['Items'][0]['shots_left'] != 'not-set':
                if int(newest_scoreboard['shots_left']) > int(response['Items'][0]['shots_left']):
                    print('SHOT team1: {} from {}'.format(newest_scoreboard['shots_left'],response['Items'][0]['shots_left']))
                    shot_object["payload"]['Team 1 Shot'] = 'true'
                    teams_shot = 'true'
            
        if newest_scoreboard['score_right'] == 'not-set':
            if response['Items'][0]['score_right'] != 'not-set':
                print('reverting score_right from: {} to {}'.format(newest_scoreboard['score_right'],response['Items'][0]['score_right']))
                newest_scoreboard['score_right'] = response['Items'][0]['score_right']
        else:
            if response['Items'][0]['score_right'] != 'not-set':
                if int(newest_scoreboard['score_right']) > int(response['Items'][0]['score_right']):
                    print('SCORE team2: {} from {}'.format(newest_scoreboard['score_right'],response['Items'][0]['score_right']))            
                    scored_object["payload"]['Team 2 Goal'] = 'true'
                    teams_scored = 'true'

        if newest_scoreboard['shots_right'] == 'not-set':
            if response['Items'][0]['shots_right'] != 'not-set':
                print('reverting shots_right from: {} to {}'.format(newest_scoreboard['shots_right'],response['Items'][0]['shots_right']))
                newest_scoreboard['shots_right'] = response['Items'][0]['shots_right']
        else:
            if response['Items'][0]['shots_right'] != 'not-set':
                if int(newest_scoreboard['shots_right']) > int(response['Items'][0]['shots_right']):
                    print('SHOT team2: {} from {}'.format(newest_scoreboard['shots_right'],response['Items'][0]['shots_right']))
                    shot_object["payload"]['Team 2 Shot'] = 'true'
                    teams_shot = 'true'

        if newest_scoreboard['game_clock'] == 'not-set':
            if response['Items'][0]['game_clock'] != 'not-set':
                print('reverting game_clock from: {} to {}'.format(newest_scoreboard['game_clock'],response['Items'][0]['game_clock']))
                newest_scoreboard['game_clock'] = response['Items'][0]['game_clock']

        if newest_scoreboard['game_period'] == 'not-set':
            if response['Items'][0]['game_period'] != 'not-set':
                print('reverting game_period from: {} to {}'.format(newest_scoreboard['game_period'],response['Items'][0]['game_period']))
                newest_scoreboard['game_period'] = response['Items'][0]['game_period']
        else:
            if response['Items'][0]['game_period'] != 'not-set':
                if int(newest_scoreboard['game_period']) != int(response['Items'][0]['game_period']):
                    print('PERIOD CHANGE game_period: {} from {}'.format(newest_scoreboard['game_period'],response['Items'][0]['game_period']))
                    period_object["payload"]['period'] = newest_scoreboard['game_period']
                    period_change = 'true'
                
    else:
        print("WARNING: no dynamoDB entries")

    scoreboard = {
        "ts": segment_datetime,
        "element_id": "-L7fPy8uipMuDS5WEXvj", 
        "payload" : {
            "Team1Name": "Winterhawks", 
            "Team1Color": {
                "solidColor" : { 
                    "a" : 1,
                    "b": 49, 
                    "g": 49, 
                    "r": 49,
                } 
            },
            "Team1Logo" : "http://linkToImage", 
            "Team1Score": newest_scoreboard['score_left'],
            "Team1Shots": newest_scoreboard['shots_left'],
            "Team2Name": "Thunderbirds", 
            "Team2Color": {
                "solidColor" : { 
                    "a" : 1,
                    "b": 113, 
                    "g": 66, 
                    "r": 224,
                } 
            },
            "Team2Logo" : "http://linkToImage", 
            "Team2Score": newest_scoreboard['score_right'],
            "Team2Shots": newest_scoreboard['shots_right'],
            "period" : newest_scoreboard['game_period'],
            "clock": newest_scoreboard['game_clock']
        },
    }

    image_filename = segment_filename.replace(".ts", "-001.jpg")
    ## SINGULAR 
    if SINGULAR_ENABLE == 'true':
        req = urllib2.Request(' http://start.singular.live/event')
        req.add_header('Content-Type', 'application/json')
        response = urllib2.urlopen(req, json.dumps(scoreboard))
        print(response.read())
    if teams_scored == 'true':
        print('SCORED: {}'.format(scored_object))
        put_dynamo_list(dynamo_object, scored_object, scoreboard, image_filename, segment_datetime, 'score')
        if SINGULAR_ENABLE == 'true':
            req = urllib2.Request(' http://start.singular.live/event')
            req.add_header('Content-Type', 'application/json')
            response = urllib2.urlopen(req, json.dumps(scored_object))
            print(response.read())
    if teams_shot == 'true':
        if teams_scored == 'false':
            print('SHOT: {}'.format(shot_object))
            put_dynamo_list(dynamo_object, shot_object, scoreboard, image_filename, segment_datetime, 'shot')
    if period_change == 'true':
        print('PERIOD CHANGE: {}'.format(shot_object))
        put_dynamo_list(dynamo_object, period_object, scoreboard, image_filename, segment_datetime, 'period')



   # write json file
    dynamo_object['label_image'] = image_filename
    json_string = json.dumps(dynamo_object)
    dynamo_filename = 'scoreboard.json'
    with open(tmpdir + dynamo_filename, 'w') as outfile:
        outfile.write(json_string)
    data = open(tmpdir + dynamo_filename, 'rb')
    print(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))
    delete_file(tmpdir + dynamo_filename)

    write_json()

    # pprint(scoreboard)
    # return scoreboard
    return 'SUCCESS: it ran'

if __name__ == '__main__':
    ''' 
    This is to run for local testing
    '''

    XRAY = 'false' # stop xray when doing local testing
    FFPROBE = 'ffprobe' # use local mac version 
    FFMPEG = 'ffmpeg' # use local mac version 
    os.environ['HLS_URL'] = 'live/stream.m3u8'
    # os.environ['HLS_URL_PLAYLIST'] = 'live/stream_540p.m3u8'
    os.environ['HLS_URL_PLAYLIST'] = 'live/stream_1.m3u8'
    # os.environ['S3_BUCKET'] = 'catfinder5004-dev'
    os.environ['S3_BUCKET'] = 'nab2018-catfinder5004'    
    os.environ['DYNAMO_MAIN'] = 'catfinder5004-main'
    os.environ['DYNAMO_LIST'] = 'catfinder5004-list'
    this_event = {
        u'Records': [
            {
                u'eventVersion': u'2.0', 
                u'eventTime': u'2018-02-28T21:49:14.591Z', 
                u'requestParameters': {u'sourceIPAddress': u'35.173.106.111'}, 
                u's3': {
                    u'configurationId': u'd40f9942-c72b-4f75-8ad6-175f96664136', 
                    u'object': 
                    {
                        u'versionId': u'MK7r.Nxr4CCGY7iy6xjQPxn5Ion1vJEJ', 
                        u'eTag': u'f6bb9089b283dd7462dfb2c7d9059389',
                        u'sequencer': u'005A9723DA8F7A27FA',
                        u'key': os.environ['HLS_URL_PLAYLIST'],
                        u'size': 783
                       },
                    u'bucket': {u'arn': 'arn:aws:s3:::' + os.environ['S3_BUCKET'], u'name': os.environ['S3_BUCKET'], u'ownerIdentity': {u'principalId': u'A3O6OAAHVNNGK1'}},
                    u's3SchemaVersion': u'1.0'
                },
                u'responseElements': {u'x-amz-id-2': u'FmenMKJg026LY8uOR1kRojwOB0DepZSEj+4TLsa9SxdwmZpPkDWSn77zFrTUC3zOrtQ/yAgkgmQ=', u'x-amz-request-id': u'80FE17847B7ED4E6'},
                u'awsRegion': u'us-east-1',
                u'eventName': u'ObjectCreated:Put',
                u'userIdentity': {u'principalId': u'AWS:AROAJAMMNNRJLENMQDXH6:container-role'},
                u'eventSource': u'aws:s3'
            }
        ]
    }
    versions = s3.Bucket(os.environ['S3_BUCKET']).object_versions.filter(Prefix=os.environ['HLS_URL_PLAYLIST'],MaxKeys=1,)
    for version in versions:
        object = version.get()
        print (object.get('VersionId'),object.get('ContentLength'))    
        this_event['Records'][0]['s3']['object']['versionId'] = object.get('VersionId')
        break
    pprint(this_event)
    print(lambda_handler(this_event, None))
    with open('deploy', 'w') as outfile:
        outfile.write('lambda-uploader --variables \'{"DYNAMO_MAIN": "' + DYNAMO_MAIN + '","DYNAMO_LIST": "' + DYNAMO_LIST + '","HLS_URL": "' + HLS_URL + '","HLS_URL_PLAYLIST": "' + HLS_URL_PLAYLIST + '","S3_BUCKET": "' + S3_BUCKET + '" }\'')
    with open('logs', 'w') as outfile:
        outfile.write('awslogs get /aws/lambda/catfinder5004-parse ALL --watch')
