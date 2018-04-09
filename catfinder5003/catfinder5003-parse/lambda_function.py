from urllib2 import urlopen as wget
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

# patch_all()
XRAY = 'true'

## these are unique and must be set
S3_BUCKET = "not-set"
HLS_URL = 'not-set'
HLS_URL_PLAYLIST = 'not-set'
CHANNEL_NAME = 'not-set'
MEDIALIVE_CHANNEL = {}
MEDIAPACKAGE_CHANNEL = {}

## hardcoded for console use
# DYNAMO_MAIN = "catfinder5002-main"
DYNAMO_MAIN_GSI = "id_type-id_filename-index"
# DYNAMO_LIST = "catfinder5002-list"
# DYNAMO_SUMMARY = "catfinder5002-summary"
DYNAMO_SUMMARY_GSI = 'rekog_type-timestamp_updated-index'
# LAMBDA_PREKOG = "catfinder5002-prekog"
REKOG_LABEL = "Cat"

FFPROBE = './ffprobe'
FFMPEG = './ffmpeg'

s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb')
rekognition = boto3.client("rekognition")
lambda_client = boto3.client('lambda')
medialive = boto3.client("medialive", region_name='us-east-1')
# transcribe = boto3.client('transcribe', region_name='us-east-1')
mediapackage = boto3.client('mediapackage')


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
    global DYNAMO_SUMMARY
    global DYNAMO_SUMMARY_GSI
    global LAMBDA_PREKOG
    global REKOG_LABEL
    global CHANNEL_NAME
    global MEDIALIVE_CHANNEL


    if os.environ.get('CHANNEL_NAME') is not None:
        CHANNEL_NAME = os.environ['CHANNEL_NAME']
        print('environment variable CHANNEL_NAME was found: {}'.format(CHANNEL_NAME))
    token = ''
    channels = []
    with _timeout(None):
        while True:
            chan = medialive.list_channels(NextToken=token)
            token = chan.get('NextToken', '')
            channels.extend(chan['Channels'])
            if token == '': break    
    for ch in channels:
        if ch['Name'] == CHANNEL_NAME:
            channel_id = ch['Id']
            print('Channel Name was matched to Channel ID: {}'.format(channel_id))
            for destination in ch['Destinations']:
                if destination['Settings'][0]['Url'].split('://')[0] == 's3':
                    S3_BUCKET = destination['Settings'][0]['Url'].split('://')[1].split('/')[0]
                    HLS_URL = "/".join(destination['Settings'][0]['Url'].split('://')[1].split('/')[1:])
            channel = medialive.describe_channel(ChannelId=channel_id)
            MEDIALIVE_CHANNEL = channel
            for outputgroup in channel['EncoderSettings']['OutputGroups']:
                if outputgroup['Name'] == 'S3 Bucket':
                    HLS_URL_PLAYLIST = HLS_URL + outputgroup['Outputs'][0]['OutputSettings']['HlsOutputSettings']['NameModifier']
            HLS_URL = HLS_URL + '.m3u8'
            HLS_URL_PLAYLIST = HLS_URL_PLAYLIST + '.m3u8'
            print('autosetting variable S3_BUCKET to: {}'.format(S3_BUCKET))
            print('autosetting variable HLS_URL to: {}'.format(HLS_URL))
            print('autosetting variable HLS_URL_PLAYLIST to: {}'.format(HLS_URL_PLAYLIST))
        else:
            print('Channel was not Found')



    if os.environ.get('S3_BUCKET') is not None:
        S3_BUCKET = os.environ['S3_BUCKET']
        print('environment variable S3_BUCKET was found: {}'.format(S3_BUCKET))
    if os.environ.get('DYNAMO_MAIN') is not None:
        DYNAMO_MAIN = os.environ['DYNAMO_MAIN']
        print('environment variable DYNAMO_MAIN was found: {}'.format(DYNAMO_MAIN))
    if os.environ.get('DYNAMO_LIST') is not None:
        DYNAMO_LIST = os.environ['DYNAMO_LIST']
        print('environment variable DYNAMO_LIST was found: {}'.format(DYNAMO_LIST))
    if os.environ.get('DYNAMO_SUMMARY') is not None:
        DYNAMO_SUMMARY = os.environ['DYNAMO_SUMMARY']
        print('environment variable DYNAMO_SUMMARY was found: {}'.format(DYNAMO_SUMMARY))
    if os.environ.get('DYNAMO_SUMMARY_GSI') is not None:
        DYNAMO_SUMMARY_GSI = os.environ['DYNAMO_SUMMARY_GSI']
        print('environment variable DYNAMO_SUMMARY_GSI was found: {}'.format(DYNAMO_SUMMARY_GSI))
    if os.environ.get('LAMBDA_PREKOG') is not None:
        LAMBDA_PREKOG = os.environ['LAMBDA_PREKOG']
        print('environment variable LAMBDA_PREKOG was found: {}'.format(LAMBDA_PREKOG))
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

def update_dyanmo_summary ( rekog_summary ):
    ## DynamoDB Update
    print("put_dynamo to table: " + str(DYNAMO_SUMMARY))
    table = dynamodb.Table(DYNAMO_SUMMARY)    # current
    response = table.update_item(
        Key={
            'rekog_label': rekog_summary['rekog_label'],
        },
        UpdateExpression="set timestamp_updated = :timestamp_updated, timestamp_ttl = :timestamp_ttl, rekog_type = :rekog_type, id_filename = :id_filename  ",
        ExpressionAttributeValues={
                ':timestamp_updated': rekog_summary['timestamp_updated'],
                ':timestamp_ttl': rekog_summary['timestamp_ttl'],
                ':rekog_type': rekog_summary['rekog_type'],
                ':id_filename': rekog_summary['id_filename'],
        },
        # ConditionExpression="job_state <> :completed",
        ReturnValues="UPDATED_NEW"
    )
    # print("dynamo update_item succeeded: {}".format(response))
    # pprint(response)

def put_dynamo_main(dynamo_object):
    print("put_dynamo to table: " + str(DYNAMO_MAIN))
    table = dynamodb.Table(DYNAMO_MAIN)
    try:
        response = table.put_item(
            Item=dynamo_object,
            ConditionExpression='attribute_not_exists(id_filename)'
        )
        print("dynamo put_item succeeded: {}".format(response))
    except Exception as e:
        # Ignore the ConditionalCheckFailedException, bubble up other exceptions.
        print("pizzaninja: {}".format(e)) 
        print('broken dynamo: {}'.format(dynamo_object))
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise e
        sys.exc_clear()
def invoke_lambda(dynamo_object):
    invoke_response = lambda_client.invoke(FunctionName=LAMBDA_PREKOG,  InvocationType='Event', Payload=json.dumps(dynamo_object, cls=DecimalEncoder))
    print("invoke: {}".format(dynamo_object))
    print("invoke " + str(LAMBDA_PREKOG) + " code: " + str(invoke_response['StatusCode']))

def write_json():

    ## set tmp directory
    tmpdir = '/tmp/' + str(uuid.uuid4()) + '/'
    ensure_dir(tmpdir)

    # print("query of table: " + str(DYNAMO_LIST))
    # table = dynamodb.Table(DYNAMO_LIST)    
    # response = table.query(
    #     Limit=5,
    #     ScanIndexForward=False,
    #     KeyConditionExpression=Key('label').eq(REKOG_LABEL),
    # )
    # json_string = json.dumps(response['Items'], cls=DecimalEncoder)
    # dynamo_filename = 'list-vod.json'
    # with open(tmpdir + dynamo_filename, 'w') as outfile:
    #     outfile.write(json_string)

    # ## S3 upload
    # data = open(tmpdir + dynamo_filename, 'rb')
    # pprint(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))
    # delete_file(tmpdir + dynamo_filename)

    # Media Services
    response = {}
    response['medialive'] = MEDIALIVE_CHANNEL
    response['mediapackage'] = MEDIAPACKAGE_CHANNEL

    response['medialive_metrics'] = get_medialive_metric_list(MEDIALIVE_CHANNEL['Id'])
    response['mediapackage_metrics'] = get_mediapackage_metric_list(MEDIAPACKAGE_CHANNEL['ChannelId'])

    json_string = json.dumps(response, cls=DecimalEncoder)
    dynamo_filename = 'list-mediaservices.json'
    with open(tmpdir + dynamo_filename, 'w') as outfile:
        outfile.write(json_string)
    data = open(tmpdir + dynamo_filename, 'rb')
    pprint(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))
    delete_file(tmpdir + dynamo_filename)

    rekog_type = 'scenechange'
    print("query of table: " + str(DYNAMO_MAIN))
    table = dynamodb.Table(DYNAMO_MAIN)    
    response = table.query(
        # Limit=1000,
        IndexName=DYNAMO_MAIN_GSI,        
        ScanIndexForward=False,
        KeyConditionExpression=Key('id_type').eq(rekog_type),
    )
    json_string = json.dumps(response['Items'], cls=DecimalEncoder)
    dynamo_filename = 'list-' + rekog_type + '.json'
    with open(tmpdir + dynamo_filename, 'w') as outfile:
        outfile.write(json_string)
    data = open(tmpdir + dynamo_filename, 'rb')
    pprint(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))
    delete_file(tmpdir + dynamo_filename)

    rekog_type = 'label'
    print("query of table: " + str(DYNAMO_SUMMARY))
    table = dynamodb.Table(DYNAMO_SUMMARY)    
    response = table.query(
        Limit=45,
        IndexName=DYNAMO_SUMMARY_GSI,        
        ScanIndexForward=False,
        KeyConditionExpression=Key('rekog_type').eq(rekog_type),
    )
    json_string = json.dumps(response['Items'], cls=DecimalEncoder)
    dynamo_filename = 'list-' + rekog_type + '.json' 
    with open(tmpdir + dynamo_filename, 'w') as outfile:
        outfile.write(json_string)
    ## S3 upload
    data = open(tmpdir + dynamo_filename, 'rb')
    pprint(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))
    delete_file(tmpdir + dynamo_filename)

    rekog_type = 'celeb'
    print("query of table: " + str(DYNAMO_SUMMARY))
    table = dynamodb.Table(DYNAMO_SUMMARY)    
    response = table.query(
        Limit=45,
        IndexName=DYNAMO_SUMMARY_GSI,        
        ScanIndexForward=False,
        KeyConditionExpression=Key('rekog_type').eq(rekog_type),
    )
    json_string = json.dumps(response['Items'], cls=DecimalEncoder)
    dynamo_filename = 'list-' + rekog_type + '.json'
    with open(tmpdir + dynamo_filename, 'w') as outfile:
        outfile.write(json_string)
    ## S3 upload
    data = open(tmpdir + dynamo_filename, 'rb')
    pprint(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))
    delete_file(tmpdir + dynamo_filename)

    rekog_type = 'word'
    print("query of table: " + str(DYNAMO_SUMMARY))
    table = dynamodb.Table(DYNAMO_SUMMARY)    
    response = table.query(
        Limit=45,
        IndexName=DYNAMO_SUMMARY_GSI,        
        ScanIndexForward=False,
        KeyConditionExpression=Key('rekog_type').eq(rekog_type),
    )
    json_string = json.dumps(response['Items'], cls=DecimalEncoder)
    dynamo_filename = 'list-' + rekog_type + '.json'
    with open(tmpdir + dynamo_filename, 'w') as outfile:
        outfile.write(json_string)
    ## S3 upload
    data = open(tmpdir + dynamo_filename, 'rb')
    pprint(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))
    delete_file(tmpdir + dynamo_filename)

def get_medialive_metric(metric_name, channel, cloudwatch):
    stat_type = 'Average'    
    availability_group = [ '0', '1']
    group_dict = { '0': 'none', '1': 'none' }
    for this_group in availability_group: 
        metric = cloudwatch.get_metric_statistics(
            Period=120,
            StartTime=datetime.datetime.utcnow() - datetime.timedelta(minutes=2),
            EndTime=datetime.datetime.utcnow(),
            Namespace='MediaLive',
            MetricName=metric_name,
            Dimensions=[
                {
                    'Name': 'Pipeline',
                    'Value': this_group,
                },
                {
                    'Name': 'ChannelId',
                    'Value': channel,
                },        
            ],
            Statistics=[
                stat_type,
            ],
        )
        # pprint(metric)    
        for dp in metric['Datapoints']:
            # print('{} [{}]: {} {}'.format(metric_name, this_group, dp[stat_type], dp['Unit']))
            group_dict[this_group] = str(dp[stat_type]) + ' ' + str(dp['Unit'])

    print('{}: \t{}, \t{}'.format(metric_name, group_dict['0'], group_dict['1']))
    return group_dict   

def get_medialive_metric_list(channel):
    print('[{}]: \t[{}], \t[{}]'.format('metric_name', 'primary', 'backup'))

    # Create CloudWatch client
    # cw_session = boto3.Session(profile_name = args['--profile'])
    cw_session = boto3.Session()
    cloudwatch = cw_session.client('cloudwatch')
    ## known metrics as of 8/19/2017
    all_metrics = {}
    all_metrics['NetworkIn'] = get_medialive_metric('NetworkIn', channel, cloudwatch)
    all_metrics['NetworkOut'] = get_medialive_metric('NetworkOut', channel, cloudwatch)
    all_metrics['SvqTime'] = get_medialive_metric('SvqTime', channel, cloudwatch)
    all_metrics['FillMsec'] = get_medialive_metric('FillMsec', channel, cloudwatch)
    all_metrics['ActiveAlerts'] = get_medialive_metric('ActiveAlerts', channel, cloudwatch)
    all_metrics['DroppedFrames'] = get_medialive_metric('DroppedFrames', channel, cloudwatch)
    all_metrics['InputVideoFrameRate'] = get_medialive_metric('InputVideoFrameRate', channel, cloudwatch)
    # print(all_metrics)
    return all_metrics    

def get_mediapackage_metric(metric_name, channel, cloudwatch):
    stat_type = 'Average'    
    if metric_name == 'EgressRequestCount':
        stat_type = 'Sum'
    group_dict = 'not-set'
    metric = cloudwatch.get_metric_statistics(
        Period=300,
        StartTime=datetime.datetime.utcnow() - datetime.timedelta(minutes=2),
        EndTime=datetime.datetime.utcnow(),
        Namespace='AWS/MediaPackage',
        MetricName=metric_name,
        Dimensions=[
            {
                'Name': 'Channel',
                'Value': channel,
            },        
        ],
        Statistics=[
            stat_type,
        ],
    )
    # pprint(metric)
    for dp in metric['Datapoints']:
        # print('{} [{}]: {} {}'.format(metric_name, this_group, dp[stat_type], dp['Unit']))
        group_dict = str(dp[stat_type]) + ' ' + str(dp['Unit'])

    print('{}: \t{}'.format(metric_name, group_dict))
    return group_dict   

def get_mediapackage_metric_list(channel):
    print('[{}]: \t[{}], \t[{}]'.format('metric_name', 'primary', 'backup'))

    # Create CloudWatch client
    # cw_session = boto3.Session(profile_name = args['--profile'])
    cw_session = boto3.Session()
    cloudwatch = cw_session.client('cloudwatch')
    ## known metrics as of 8/19/2017
    all_metrics = {}
    all_metrics['EgressBytes'] = get_mediapackage_metric('EgressBytes', channel, cloudwatch)
    all_metrics['IngressBytes'] = get_mediapackage_metric('IngressBytes', channel, cloudwatch)
    all_metrics['EgressResponseTime'] = get_mediapackage_metric('EgressResponseTime', channel, cloudwatch)
    all_metrics['EgressRequestCount'] = get_mediapackage_metric('EgressRequestCount', channel, cloudwatch)
    all_metrics['IngressResponseTime'] = get_mediapackage_metric('IngressResponseTime', channel, cloudwatch)
    # print(all_metrics)
    return all_metrics  

def media_services_info():
    global MEDIAPACKAGE_CHANNEL
    endpoints = mediapackage.list_origin_endpoints()
    for endpoint in endpoints['OriginEndpoints']:
        if endpoint['Id'] == CHANNEL_NAME + '-p_endpoint':
            MEDIAPACKAGE_CHANNEL = endpoint

segment_duration = 10
def lambda_handler(event, context):
    if XRAY == 'true':
        patch_all()    
    get_environment_variables()  
    media_services_info()
    print('S3_BUCKET: {}'.format(S3_BUCKET))
    print('HLS_URL: {}'.format(HLS_URL))
    print('HLS_URL_PLAYLIST: {}'.format(HLS_URL_PLAYLIST))
    master_ttl = 3600
    if(HLS_URL_PLAYLIST != urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))):
        return 'wrong manifest'
    # s3_version = event['Records'][0]['s3']['object']['versionId']
    # PARSE manifest
    print("master manifest: " + HLS_URL)

    # wrangle the urls
    base_url = 'live/'
    print("baseurl: {}".format(base_url))
    filename_master = HLS_URL.split('/')[-1]
    print("filename_master: {}".format(filename_master))

    ## set tmp directory
    tmpdir = '/tmp/' + str(uuid.uuid4()) + '/'
    ensure_dir(tmpdir)

    # GET master manifest
    get_s3file(S3_BUCKET, HLS_URL, tmpdir + filename_master)
    string_master = open(tmpdir + filename_master, 'r').read()
    # print("string_master: {}".format(string_master))

    # PARSE frame rate for the segments
    segment_framerate = float(string_master.split('FRAME-RATE=')[1].split(',')[0])
    print("segment_framerate: {}".format(segment_framerate))

    ## Note: this is not needed, but could use it as a checksum 
    # PARSE the m3u8 child manifestss. Returns list of these strings
    # filename_playlists = [x for x in string_master.split('\n') if '.m3u8' in x]
    # print("filename_playlists: {}".format(filename_playlists))
    
    filename_playlist = HLS_URL_PLAYLIST.split('/')[-1]
    print("filename_playlist: {}".format(filename_playlist))

    # GET child manifest
    get_s3file(S3_BUCKET, HLS_URL_PLAYLIST, tmpdir + filename_playlist)
    string_playlist = open(tmpdir + filename_playlist, 'r').read()
    # print("string_playlist: {}".format(string_playlist))

    # PARSE list of DATE-time and segment name and get last one
    segment_datetime = ''
    # segment_duration = ''
    segment_filename = ''
    for x in string_playlist.split('#EXT-X-PROGRAM-DATE-TIME:'):
        if '.ts' in x:
            segment_datetime = x.split('\n#EXTINF')[0]
            segment_duration = x.split('#EXTINF:')[1].split(',\n')[0]
            segment_filename = x.split('#EXTINF:')[1].split(',\n')[1].split('\n')[0]
    print('segment_datetime: {}'.format(segment_datetime))
    print('segment_duration: {}'.format(segment_duration))
    print('segment_filename: {}'.format(segment_filename))

    # get date time string without decimal 
    datetime_full = segment_datetime.split('.')[0] + 'Z'
    print('datetime_full: {}'.format(datetime_full))

    # get datetime object from date time string without decimal
    datetime_datetime = datetime.datetime.strptime(datetime_full, "%Y-%m-%dT%H:%M:%SZ")
    print('datetime_datetime: {}'.format(datetime_datetime))

    # get epoch of datetime
    epoch = datetime.datetime(1970,1,1)
    datetime_epoch = (datetime_datetime - epoch).total_seconds()
    print('datetime_epoch: {}'.format(datetime_epoch))

    # get the decimal from the date time string 
    datetime_decimal = segment_datetime.split('.')[1].split('Z')[:-1]
    print('datetime_decimal: {}'.format(datetime_decimal[0]))

    # convert decimal to frame number 
    datetime_frame = int(round(int(datetime_decimal[0]) * segment_framerate / 1000, 3))
    print('datetime_frame: {}'.format(datetime_frame))

    # how many frames per segment 
    frames_total = int(round(float(segment_duration) * segment_framerate, 3))
    print('frames_total: {}'.format(frames_total))

    # get filenames assumption started
    filename_base = segment_filename.split('.ts')[0]
    print('filename_base: {}'.format(filename_base))

    # get the physical segment file
    get_s3file(S3_BUCKET, base_url + segment_filename, tmpdir + segment_filename)

    ### FFPROBE - get start PTS time
    output_ffprobe1 = os.popen(FFPROBE + ' ' + tmpdir + segment_filename + ' -v quiet -show_streams -of json ').read()
    ffprobe_json1 = json.loads(output_ffprobe1)
    start_time = ffprobe_json1['streams'][0]['start_time']
    print('start_time: {}'.format(start_time))
    
    ### FFPROBE - get scene change information
    output_ffprobe = os.popen(FFPROBE + ' -v quiet -show_streams -show_frames -of json -f lavfi "movie=' + tmpdir + segment_filename + ',select=gt(scene\,.1)"').read()
    ffprobe_json = json.loads(output_ffprobe)
    scenedetect = {}
    for f in ffprobe_json['frames']:
        this_time = float(f['pkt_pts_time']) - float(start_time)
        this_frame = int(round(this_time * int(segment_framerate) + 1, 0))
        this_percent = int(round(float(f['tags']['lavfi.scene_score']),2) * 100)
        print('scenechange \tthis_frame: {} \tthis_percent: {}%'.format(this_frame, this_percent))
        scenedetect[str(this_frame)] = this_percent
    pprint(scenedetect)

    ## FFMPEG - generate a wav file
    wav_ffmpeg = os.popen(FFMPEG + ' -hide_banner -nostats -loglevel error -y -i ' + tmpdir + segment_filename + ' -vn -acodec pcm_s16le -ab 64k -ar 16k -ac 1 "' + tmpdir + filename_base + '.wav"  > /dev/null 2>&1 ').read()
    ## S3 upload
    data = open(tmpdir + filename_base + '.wav', 'rb')
    pprint(s3.Bucket(S3_BUCKET).put_object(Key='audio/' + filename_base + '.wav', Body=data))
    delete_file(tmpdir + filename_base + '.wav')
    ## TODO - trigger trainscribe lambda

    ## info for the whole segment
    dynamo_segment_object={
        'id_filename': filename_base + '.ts',
        'id_type': 'segment',
        'timestamp_minute': datetime_datetime.strftime("%Y-%m-%d %H:%M"),
        'timestamp_second': datetime_datetime.strftime("%S"),
        'timestamp_frame' : datetime_frame,
        'timestamp_pdt' : segment_datetime,
        'framerate' : str(segment_framerate),
        'duration' : segment_duration,
        'audio_file': filename_base + '.wav', 
        'transcribe_status' : 'NOT_SUBMITTED',
        'timestamp_created' : int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds()),
        'timestamp_ttl' : int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + master_ttl) # 2 hours
    }
    # raise SystemExit(0)
    
    ## FFMPEG - generate a jpg for each frame
    output_ffmpeg = os.popen(FFMPEG + ' -hide_banner -nostats -loglevel error -y -i ' + tmpdir + segment_filename + ' -an -sn -vcodec mjpeg -pix_fmt yuvj420p -qscale 1 -b:v 2000 -bt 20M "' + tmpdir + filename_base + '-%03d.jpg"  > /dev/null 2>&1 ').read()
    # delete ts segment
    myfile = tmpdir + segment_filename
    delete_file(myfile)

    scenechange_list = []

    # roll file names to next second after total fps 
    x_frame = datetime_frame
    x_filename = 1
    ## Cycle through all frames
    for x in xrange(0, frames_total):
        if x_frame >= int(segment_framerate):
            x_frame = 0
            datetime_datetime = datetime_datetime + datetime.timedelta(seconds=1)
        dynamo_epoch = (datetime_datetime - epoch).total_seconds() + (x_frame * 0.01 )
        dynamo_minute = datetime_datetime.strftime("%Y-%m-%d %H:%M")
        dynamo_second = datetime_datetime.strftime("%S")
        dynamo_frame = str(x_frame)
        dynamo_filename = filename_base + '-' + str(x_filename).zfill(3) + '.jpg'

        dynamo_object = {}
        dynamo_object={
                'id_filename': dynamo_filename,
                'id_type': 'scenechange',
                'timestamp_minute': dynamo_minute,
                'timestamp_second': dynamo_second,
                'timestamp_frame' : dynamo_frame,
                'timestamp_epoch': Decimal(dynamo_epoch),
                'timestamp_created' : int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds()),
                'timestamp_ttl' : int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + master_ttl) # 2 hours
        }
        ## Check for Scene Detection on this frame
        if str(x_filename) in scenedetect:
            ## S3 upload
            data = open(tmpdir + dynamo_filename, 'rb')
            pprint(s3.Bucket(S3_BUCKET).put_object(Key='images/' + dynamo_filename, Body=data))

            dynamo_object['scenedetect'] = str(scenedetect[str(x_filename)])
            # dynamo_object['scenedetect_round'] = str(int(round(scenedetect[str(x_filename)], -1)))

            ## Run Rekog if scene change is above 10 
            if scenedetect[str(x_filename)] > 10:
                ## REKOGNTION -- Labels
                print("starting rekog.... scenedetect is: " + str(scenedetect[str(x_filename)]))
                response = rekognition.detect_labels(Image={"S3Object": {"Bucket": S3_BUCKET, "Name": 'images/' + dynamo_filename}},MaxLabels=24)
                rekog_labels_list = []
                person_ok = 0
                text_ok = 0
                for obj in response['Labels']:
                    rekog_labels_list.append({'Confidence': str(int(round(obj['Confidence']))), 'Name': obj['Name']})
                    ## deltafa-summary
                    rekog_summary_dynamo = {}
                    rekog_summary_dynamo['scenedetect'] = str(scenedetect[str(x_filename)])
                    rekog_summary_dynamo['rekog_label'] = obj['Name']
                    rekog_summary_dynamo['rekog_type'] = 'label'
                    rekog_summary_dynamo['id_filename'] = dynamo_filename
                    rekog_summary_dynamo['timestamp_updated'] = int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds())
                    rekog_summary_dynamo['timestamp_ttl'] = int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + master_ttl )
                    update_dyanmo_summary(rekog_summary_dynamo)

                    ## Found Label, send over to PREKOG lambda
                    if rekog_summary_dynamo['rekog_label'] == REKOG_LABEL:
                        dynamo_object['rekog_label'] = obj['Name']
                        # invoke_lambda(dynamo_object)

                    # if int(round(obj['Confidence'])) > 49:
                        update_dyanmo_summary(rekog_summary_dynamo)
                    if obj['Name'] == 'Text' or obj['Name'] == 'Poster':
                        text_ok = 1
                    if obj['Name'] == 'Person':
                        person_ok = 1
                rekog_labels = sorted(rekog_labels_list, key=lambda obj: obj['Confidence'])
                print('rekog labels: {}'.format(rekog_labels))
                dynamo_object['rekog_labels'] = rekog_labels
                ## REKOGNTION -- Text
                if text_ok == 1:
                    print("rekog found Text, running OCR....")                
                    rekog_word_list = []
                    rekog_text = rekognition.detect_text(Image={"S3Object": {"Bucket": S3_BUCKET, "Name": 'images/' + dynamo_filename}})
                    print('rekog words: {}'.format(rekog_text))
                    if rekog_text['TextDetections']:
                        print('rekog found text in the image')
                        for obj in rekog_text['TextDetections']:
                            if obj['Type'] == 'WORD' or obj['Type'] == 'LINE':
                                rekog_word_list.append({'Confidence': str(int(round(obj['Confidence']))), 'Name': obj['DetectedText']})
                                ## deltafa-summary
                                rekog_summary_dynamo = {}
                                rekog_summary_dynamo['scenedetect'] = str(scenedetect[str(x_filename)])
                                rekog_summary_dynamo['rekog_label'] = obj['DetectedText']
                                rekog_summary_dynamo['rekog_type'] = 'word'
                                rekog_summary_dynamo['id_filename'] = dynamo_filename
                                rekog_summary_dynamo['timestamp_updated'] = int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds())
                                rekog_summary_dynamo['timestamp_ttl'] = int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + master_ttl)
                                update_dyanmo_summary(rekog_summary_dynamo)

                                ## Found Label, send over to PREKOG lambda
                                if rekog_summary_dynamo['rekog_label'].upper() == REKOG_LABEL.upper():
                                    dynamo_object['rekog_label'] = obj['Name']
                                    # invoke_lambda(dynamo_object)

                        print('rekog words: {}'.format(rekog_word_list))
                        dynamo_object['rekog_words'] = rekog_word_list      
                    else:
                        print('rekog did NOT find words...')
                ## REKOGNTION -- Celeb
                if person_ok == 1:
                    print("rekog found a Person, running celeb....")                
                    rekog_celebs = rekognition.recognize_celebrities(Image={"S3Object": {"Bucket": S3_BUCKET, "Name": 'images/' + dynamo_filename}})
                    print('rekog_celebs: {}'.format(rekog_celebs))
                    if rekog_celebs['CelebrityFaces']:
                        print("rekog found a celeb...")
                        rekog_celebs_list = []
                        for obj in rekog_celebs['CelebrityFaces']:
                            # invoke_lambda( rekog_label_dynamo  ) 
                            ## deltafa-summary
                            rekog_summary_dynamo = {}
                            rekog_summary_dynamo['scenedetect'] = str(scenedetect[str(x_filename)])
                            rekog_summary_dynamo['rekog_label'] = obj['Name']
                            rekog_summary_dynamo['rekog_type'] = 'celeb'
                            rekog_summary_dynamo['id_filename'] = dynamo_filename
                            rekog_summary_dynamo['timestamp_updated'] = int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds())
                            rekog_summary_dynamo['timestamp_ttl'] = int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + master_ttl)
                            update_dyanmo_summary(rekog_summary_dynamo)

                        print('rekgo celeb: {}'.format(rekog_celebs_list))
                        dynamo_object['rekog_celebs'] = rekog_celebs_list
                    else:
                        print("rekog did NOT find celeb...")
                    print("rekog found a Person, running facial....")                
                    rekog_facial = rekognition.detect_faces(
                        Image={ "S3Object": { "Bucket": S3_BUCKET, "Name": 'images/' + dynamo_filename } },
                        Attributes=['ALL'],
                        )
                    print('rekog_facial: {}'.format(rekog_facial))
                    if rekog_facial['FaceDetails']:
                        print("rekog found a facial...")
                        rekog_facial_list = []
                        for stuff in rekog_facial['FaceDetails']:
                            for obj in stuff:
                                if obj == 'AgeRange':
                                    age = 'Age ' + str(stuff[obj]['Low']) + '-' + str(stuff[obj]['High'])
                                    rekog_facial_list.append(age)
                                if obj == 'Smile' and stuff[obj]['Value'] == True:
                                    rekog_facial_list.append(obj)
                                if obj == 'Mustache' and stuff[obj]['Value'] == True:
                                    rekog_facial_list.append(obj)
                                if obj == 'Beard' and stuff[obj]['Value'] == True:
                                    rekog_facial_list.append(obj)
                                if obj == 'Eyeglasses' and stuff[obj]['Value'] == True:
                                    rekog_facial_list.append(obj)
                                if obj == 'Sunglasses' and stuff[obj]['Value'] == True:
                                    rekog_facial_list.append(obj)
                                if obj == 'MouthOpen' and stuff[obj]['Value'] == True:
                                    rekog_facial_list.append(obj)
                                if obj == 'EyesOpen' and stuff[obj]['Value'] == True:
                                    rekog_facial_list.append(obj)            
                                if obj == 'Gender' and stuff[obj]['Confidence'] > 70:
                                    rekog_facial_list.append(stuff[obj]['Value'])
                                if obj == 'Emotions':
                                    for emot in stuff[obj]:
                                        rekog_facial_list.append(emot['Type'])
                        print('rekog_facial_list: {}'.format(rekog_facial_list))
                        dynamo_object['rekog_facial'] = rekog_facial_list                            
                    else:
                        print("rekog did NOT find facial...")
                    
                # PUT DYNAMO - main
                put_dynamo_main(dynamo_object)
                scenechange_list.append(dynamo_object['id_filename'])                
        # clean up jpgs
        delete_file(tmpdir + dynamo_filename)

        x_frame += 1
        x_filename += 1    

    # full segment information 
    dynamo_segment_object['scenechange_list'] = scenechange_list
    pprint(dynamo_segment_object)
    put_dynamo_main(dynamo_segment_object)

    write_json()
    return 'SUCCESS: it ran'

if __name__ == '__main__':
    ''' 
    This is to run for local testing
    '''

    XRAY = 'false' # stop xray when doing local testing
    FFPROBE = 'ffprobe' # use local mac version 
    FFMPEG = 'ffmpeg' # use local mac version 
    # os.environ['HLS_URL'] = 'live/stream.m3u8'
    # os.environ['HLS_URL_PLAYLIST'] = 'live/stream_1.m3u8'
    # os.environ['S3_BUCKET'] = 'ces2018-demo'
    os.environ['CHANNEL_NAME'] =  'nab2018-catfinder5003'
    os.environ['DYNAMO_MAIN'] = 'nab2018-catfinder5003-main'    
    os.environ['DYNAMO_SUMMARY'] = 'nab2018-catfinder5003-summary'
    # os.environ['DYNAMO_LIST'] = 'catfinder5002-list'
    os.environ['REKOG_LABEL'] = 'Cat'
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
                        u'key': u'live/stream_1.m3u8',
                        u'size': 783
                       },
                    u'bucket': {u'arn': u'arn:aws:s3:::catfinder5002-test', u'name': u'catfinder5002-test', u'ownerIdentity': {u'principalId': u'A3O6OAAHVNNGK1'}},
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
    print(lambda_handler(this_event, None))
    with open('deploy', 'w') as outfile:
        outfile.write('lambda-uploader --variables \'{"CHANNEL_NAME": "' + CHANNEL_NAME + '","DYNAMO_MAIN": "' + DYNAMO_MAIN + '","DYNAMO_SUMMARY": "' + DYNAMO_SUMMARY + '" }\'')
    with open('logs', 'w') as outfile:
        outfile.write('awslogs get /aws/lambda/catfinder5002-parse ALL --watch')
