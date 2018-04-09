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

## figure this out later

HLS_URL = 'live/stream.m3u8'
HLS_URL_PLAYLIST = 'live/stream_1.m3u8'
S3_BUCKET = 'ces2018-demo'
CHANNEL_NAME =  'ces2018'
    
## these are unique and must be set
S3_BUCKET = "not-set"
HLS_URL = 'not-set'
HLS_URL_PLAYLIST = 'not-set'
CHANNEL_NAME = 'not-set'

## hardcoded for console use
DYNAMO_MAIN = "ces2018-main"
DYNAMO_LIST = "ces2018-list"
DYNAMO_SUMMARY = "ces2018-summary"
DYNAMO_SUMMARY_GSI = 'rekog_type-timestamp_updated-index'
LAMBDA_PREKOG = "ces2018-prekog"
REKOG_LABEL = "Cat"

## figure this out later

HLS_URL = 'live/stream.m3u8'
HLS_URL_PLAYLIST = 'live/stream_1.m3u8'
S3_BUCKET = 'ces2018-demo'
CHANNEL_NAME =  'ces2018'

FFPROBE = './ffprobe'
FFMPEG = './ffmpeg'

# s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb')
# rekognition = boto3.client("rekognition")
# lambda_client = boto3.client('lambda')
# medialive = boto3.client("medialive", region_name='us-east-1')
# transcribe = boto3.client('transcribe', region_name='us-east-1')


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


    if os.environ.get('CHANNEL_NAME') is not None:
        CHANNEL_NAME = os.environ['CHANNEL_NAME']
        print('environment variable CHANNEL_NAME was found: {}'.format(CHANNEL_NAME))

    # channel_id = '5144035'
    # channels = medialive.list_channels()
    # pprint(channels)
    # for channel in channels['Channels']:
    #     if channel['Name'] == CHANNEL_NAME:
    #         channel_id = channel['Id']
    #         for destination in channel['Destinations']:
    #             if destination['Settings'][0]['Url'].split('://')[0] == 's3':
    #                 S3_BUCKET = destination['Settings'][0]['Url'].split('://')[1].split('/')[0]
    #                 HLS_URL = "/".join(destination['Settings'][0]['Url'].split('://')[1].split('/')[1:])
    # channel = medialive.describe_channel(ChannelId=channel_id)
    # for outputgroup in channel['EncoderSettings']['OutputGroups']:
    #     if outputgroup['Name'] == 'S3':
    #         HLS_URL_PLAYLIST = HLS_URL + outputgroup['Outputs'][0]['OutputSettings']['HlsOutputSettings']['NameModifier']
    # HLS_URL = HLS_URL + '.m3u8'
    # HLS_URL_PLAYLIST = HLS_URL_PLAYLIST + '.m3u8'
    # print('autosetting variable S3_BUCKET to: {}'.format(S3_BUCKET))
    # print('autosetting variable HLS_URL to: {}'.format(HLS_URL))
    # print('autosetting variable HLS_URL_PLAYLIST to: {}'.format(HLS_URL_PLAYLIST))


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

def get_dynamo_summary(rekog_type):
    print("query of table: " + str(DYNAMO_SUMMARY))
    table = dynamodb.Table(DYNAMO_SUMMARY)    
    response = table.query(
        Limit=30,
        IndexName=DYNAMO_SUMMARY_GSI,        
        ScanIndexForward=False,
        KeyConditionExpression=Key('rekog_type').eq(rekog_type) & Key('timestamp_updated').gt(int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() - 60)),
    )     
    return response['Items']

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


def lambda_handler(event, context):
    if XRAY == 'true':
        patch_all()    
    get_environment_variables()  
    timestamp_start = (datetime.datetime.now() - datetime.timedelta(seconds=60))
    timestamp_end = datetime.datetime.now()
    timestamps = {
        'start' : "{:%b %d, %H:%M:%S}".format(timestamp_start),
        'end' : "{:%b %d, %H:%M:%S}".format(timestamp_end),
    }
    print('timestamps: {}'.format(timestamps))
    full_list = [] 
    images_list = {}
    rekog_type = 'label'
    this_response = get_dynamo_summary(rekog_type)
    for stuff in this_response:
        full_list.append(stuff['rekog_label'].lower())
        # images_list.append({stuff['rekog_label'].lower() : stuff['id_filename']})
        images_list[stuff['rekog_label'].lower()] = stuff['id_filename']
    rekog_type = 'word'
    this_response = get_dynamo_summary(rekog_type)
    for stuff in this_response:
        full_list.append(stuff['rekog_label'].lower())
        # images_list.append({stuff['rekog_label'].lower() : stuff['id_filename']})
        images_list[stuff['rekog_label'].lower()] = stuff['id_filename']        

    print('full list: {}'.format(full_list))
    print('images list: {}'.format(images_list))

    # boulder eats: [u'girl', u'salad', u'human', u'woman', u'blonde', u'food', u'dinner', u'face', u'bowl', u'supper', u'lunch', u'female', u'person', u'meal', u'people', u'portrait', u'sport', u'sports', u'working out', u'produce', u'exercise', u'long sleeve', u'dahlia', u'sprout', u'daisy', u'clothing', u'flora', u'ornament', u'daisies', u'flower']
    # top gear: [u'human', u'vehicle', u'transportation', u'face', u'automobile', u'driving', u'person', u'people', u'portrait', u'car', u'convertible', u'apparel', u'shoe', u'clothing', u'footwear', u'wedge', u'triangle', u'laptop', u'pc', u'computer', u'electronics', u'bumper', u'white board', u'mold', u'adorable', u'sink', u'coupe', u'sports car', u'arm', u'airport']
    # top gear 2: [u'human', u'vehicle', u'transportation', u'face', u'automobile', u'driving', u'person', u'people', u'portrait', u'car', u'convertible', u'apparel', u'shoe', u'clothing', u'footwear', u'wedge', u'triangle', u'laptop', u'pc', u'computer', u'electronics', u'bumper', u'white board', u'mold', u'adorable', u'sink', u'coupe', u'sports car', u'arm', u'airport']
    # zoo bear: [u'mammal', u'hole', u'bear', u'wildlife', u'animal', u'zoo', u'astronomy', u'space', u'universe', u'outer space']
    # hockey: [u'skating', u'human', u'team sport', u'hockey', u'sport', u'ice hockey', u'team', u'ice skating', u'sports', u'person', u'rink', u'people', u'modern art', u'art']
    match_list = {
        'formula_racing' : ['road', 'street', 'vehicle', 'wheel' ],
        'moods_tour' : ['instrument', 'band', 'guitar', 'city', 'alcohol'],
        'odeur' : ['clothing', 'flora'],
        'robots' : ['toys', 'electronics'],
        'save_polarbear' : ['animal', 'bear', 'cat', 'dog'],
        'sportz' : ['baseball', 'football', 'basketball', 'hockey', 'sports'],
        'visit_alps' : ['ski', 'snow', 'powder', 'luggage',],
        'visit_caribbean' : ['beach', 'sun', 'drinks', 'nature', 'weather', 'sunset' ],
        'g_i_joe' : ['toy', 'sport', 'outdoors'],
        'candy_bar' : ['salad'],
        'video_game' : ['watch', 'television', 'electronics'],
        'super_boy' : ['grass', 'outer space', ],
        'toy_puppy' : ['toy', 'dog', 'zoo', 'bird'],
        'action_figure' : ['toy', 'gun', 'motorcycle', ],
        # 'toy_car' : ['toy', 'car', 'electronics'],
        'chocoloate_drink' : ['drinks', 'food', 'lunch'],
        # 'soft_drink' : ['drinks', 'glass', 'beverage'],

    }
    thirty_secs = [
        'g_i_joe',
        'candy_bar',
        'video_game',
        'super_boy',
        'toy_puppy',
        'action_figure',
        'toy_car',
        'chocoloate_drink',
        'soft_drink',
    ]
    ad_playlist = []
    ad_matches = []
    images_matches = {}
    for ad_type in match_list:
        for ad_label in match_list[ad_type]:
            if ad_label in full_list:
                print('MATCHED! type: {} \tlabel: {}'.format(ad_type,ad_label))
                ad_playlist.append(ad_type)
                ad_matches.append({ad_type : ad_label})
                images_matches[ad_label] = {'image' : images_list[ad_label], 'type': ad_type }
    print('images_matches: {}'.format(images_matches))
    # pprint(ad_playlist)
    if len(ad_playlist) < 1:
        ad_playlist.append('default')
    while len(ad_playlist) < 5:
        ad_playlist.extend(ad_playlist)
    print('playlist lineup: {}'.format(ad_playlist))

    full_xml = '''<VAST version="3.0">
'''
    x = 0
    for ad in ad_playlist:
        duration = '00:00:15'
        if ad in thirty_secs:
            duration = '00:00:30'
        x += 1
        full_xml += '''
    <Ad sequence="''' + str(x) + '''">
        <InLine>
            <AdSystem>2.0</AdSystem>
            <AdTitle>ad-''' + str(x) + '''</AdTitle>
            <Impression></Impression>
            <Creatives>
                <Creative id="''' + str(ad) + '''-3">
                    <Linear>
                        <Duration>''' + str(duration) + '''</Duration>
                        <TrackingEvents></TrackingEvents>
                        <MediaFiles>
                            <MediaFile delivery="progressive" type="video/mp4" width="1920" height="1080">
                                <![CDATA[
                                    https://s3.amazonaws.com/ces2018-demo/ads/''' + ad + '''-3.mp4
                                ]]>
                            </MediaFile>
                        </MediaFiles>
                    </Linear>
                </Creative>
            </Creatives>
        </InLine>
    </Ad> '''

    full_xml += '''
</VAST>'''
    # print('xml: {}'.format(full_xml))
    json_together = {
        # 'full_list' : full_list,
        'matches' : ad_matches,
        'images_list' : images_list,
        'images_matches' : images_matches,
        'timestamps' : timestamps,
    }
    # pprint(json_together)
    json_string = json.dumps(json_together, cls=DecimalEncoder)
    dynamo_filename = 'list-ads.json'
    ## set tmp directory
    tmpdir = '/tmp/' + str(uuid.uuid4()) + '/'
    ensure_dir(tmpdir)
    with open(tmpdir + dynamo_filename, 'w') as outfile:
        outfile.write(json_string)
    ## S3 upload
    data = open(tmpdir + dynamo_filename, 'rb')
    s3 = boto3.resource('s3')
    pprint(s3.Bucket(S3_BUCKET).put_object(Key=dynamo_filename, Body=data))  

    return {
        'statusCode': '200',
        # 'body': re.sub(r'(.+m3u8|.+ts)', base_url + r'\1', master,re.M),
        'body': full_xml,
        'headers': {'Content-Type': 'application/xml', 'Access-Control-Allow-Origin': '*'}
    }
if __name__ == '__main__':
    ''' 
    This is to run for local testing
    '''

    XRAY = 'false' # stop xray when doing local testing

    # print(lambda_handler(None, None))
    lambda_handler(None, None)
    # print('UPLOAD Command: \tlambda-uploader --variables \'{"CHANNEL_NAME": "' + CHANNEL_NAME + '" }\'')
