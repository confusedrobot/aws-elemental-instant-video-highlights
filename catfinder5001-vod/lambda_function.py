from urllib2 import urlopen as wget
import urllib
import urllib2
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


XRAY = 'true'

# overwritten from event
EMC_ROLE = 'not-set'
EMC_ENDPOINT = 'not-set'

S3_BUCKET = 'not-set'
DYNAMO_LIST = 'not-set'


s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb')


def get_environment_variables():
    global EMC_ROLE
    global EMC_ENDPOINT
    
    global S3_BUCKET
    global DYNAMO_LIST

    if os.environ.get('EMC_ROLE') is not None:
        EMC_ROLE = os.environ['EMC_ROLE']
        print('environment variable EMC_ROLE was found: {}'.format(EMC_ROLE))
    if os.environ.get('EMC_ENDPOINT') is not None:
        EMC_ENDPOINT = os.environ['EMC_ENDPOINT']
        print('environment variable EMC_ENDPOINT was found: {}'.format(EMC_ENDPOINT))

    if os.environ.get('S3_BUCKET') is not None:
        S3_BUCKET = os.environ['S3_BUCKET']
        print('environment variable S3_BUCKET was found: {}'.format(S3_BUCKET))
    if os.environ.get('DYNAMO_LIST') is not None:
        DYNAMO_LIST = os.environ['DYNAMO_LIST']
        print('environment variable DYNAMO_LIST was found: {}'.format(DYNAMO_LIST))


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

def update_dyanmo_list ( rekog_summary ):
    ## DynamoDB Update
    print("put_dynamo to table: " + str(DYNAMO_LIST))
    table = dynamodb.Table(DYNAMO_LIST)    # current
    response = table.update_item(
        Key={
            'label': rekog_summary['label'],
            'label_sort': rekog_summary['label_sort'],
        },
        UpdateExpression="set emc_url = :emc_url, emc_status = :emc_status",
        ExpressionAttributeValues={
                ':emc_url': rekog_summary['emc_url'],
                ':emc_status': rekog_summary['emc_status'],
        },
        # ConditionExpression="job_state <> :completed",
        ReturnValues="UPDATED_NEW"
    )
    print("dynamo update_item succeeded: {}".format(response))
    # pprint(response)


def lambda_handler(event, context):
    if XRAY == 'true':
        patch_all()

    ### SNS from MediaConvert
    if 'detail-type' in event:
        if event['detail-type'] == 'MediaConvert Job State Change':
            emc_list = {
                'label' : event['detail']['userMetadata']['label'],
                'label_sort' : event['detail']['userMetadata']['label_sort'],
                'emc_url' : event['detail']['userMetadata']['label_sort'] + '_video.mp4' ,
                'emc_status' : event['detail']['status'],
            }
            update_dyanmo_list ( emc_list )
    else:

        # set here because of global variable
        mediaconvert = boto3.client('mediaconvert', endpoint_url=EMC_ENDPOINT)
        
        master_ttl = 3600
        url_full = event['emp_url']
        s3_bucket = event['s3_bucket']
        event_id = event['label_sort']
        # PARSE manifest
        print("master manifest: " + url_full)

        # wrangle the urls
        base_url = '/'.join(url_full.split('/')[:-1]) + '/'
        print("baseurl: {}".format(base_url))
        filename_master = url_full.split('/')[-1]
        print("filename_master: {}".format(filename_master))

        # GET master manifest
        string_master = get_url(base_url + filename_master)
        print("string_master: {}".format(string_master))

        # PARSE the m3u8 child manifestss. Returns list of these strings
        filename_playlists = [x for x in string_master.split('\n') if '.m3u8' in x]
        print("filename_playlists: {}".format(filename_playlists))

        # GET child manifest
        string_playlist = get_url(base_url + filename_playlists[0])
        print("string_playlist: {}".format(string_playlist))

        # get filenames assumption started
        # filename_base = segment_filename.split('.ts')[0]
        # print('filename_base: {}'.format(filename_base))

        ## set tmp directory
        tmpdir = '/tmp/' + event_id + '/'
        ensure_dir(tmpdir)
        print('tmpdir: {}'.format(tmpdir))

        # get the physical master manifest file
        save_file(tmpdir + filename_master.split('?')[0], get_url(base_url + filename_master))
        data = open(tmpdir + filename_master.split('?')[0], 'rb')
        pprint(s3.Bucket(s3_bucket).put_object(Key='video' + tmpdir + filename_master.split('?')[0], Body=data))
        delete_file(tmpdir + filename_master.split('?')[0])

        # get the physical child manifest file
        save_file(tmpdir + filename_playlists[0].split('?')[0], get_url(base_url + filename_playlists[0]))
        data = open(tmpdir + filename_playlists[0].split('?')[0], 'rb')
        pprint(s3.Bucket(s3_bucket).put_object(Key='video' + tmpdir + filename_playlists[0].split('?')[0], Body=data))
        delete_file(tmpdir + filename_playlists[0].split('?')[0])


        # get the physical segment file
        for x in string_playlist.split('\n'):
            if '.ts' in x:
                pprint(x)
                segment_filename = x.split('?')[0]
                save_file(tmpdir + segment_filename, get_url(base_url + segment_filename))
                data = open(tmpdir + segment_filename, 'rb')
                pprint(s3.Bucket(s3_bucket).put_object(Key='video' + tmpdir + segment_filename, Body=data))
                delete_file(tmpdir + segment_filename)


        ## MediaConvert 
        # mediaConvertRole = "arn:aws:iam::463540299421:role/vod-MediaConvertIAMRole-1BIVDOODMZT1L-MediaConvertRole"
        # mediaConvertEndpoint = "https://vweb51sm.mediaconvert.us-west-2.amazonaws.com"
        time_start = str(event['time_start'].split(' ')[1]) + ":" + event['time_start_frame'].zfill(2)
        time_end =  str(event['time_end'].split(' ')[1]) + ":" + event['time_end_frame'].zfill(2)

        # time_start = event['time_start'].split(' ')[1]
        # time_end = event['time_end'].split(' ')[1]
        # mediaconvert = boto3.client('mediaconvert', endpoint_url=EMC_ENDPOINT)
        jobMetadata = {'label_sort': str(event['label_sort']), 'label': str(event['label']) }
        jobSettings = {
        "OutputGroups": [
        {
            "Name": "File Group",
            "Outputs": [
            {
                "ContainerSettings": {
                "Container": "MP4",
                "Mp4Settings": {
                    "CslgAtom": "INCLUDE",
                    "FreeSpaceBox": "EXCLUDE",
                    "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                }
                },
                "VideoDescription": {
                "Width": 1280,
                "ScalingBehavior": "DEFAULT",
                "Height": 720,
                "TimecodeInsertion": "DISABLED",
                "AntiAlias": "ENABLED",
                "Sharpness": 50,
                "CodecSettings": {
                    "Codec": "H_264",
                    "H264Settings": {
                    "InterlaceMode": "PROGRESSIVE",
                    "NumberReferenceFrames": 3,
                    "Syntax": "DEFAULT",
                    "Softness": 0,
                    "GopClosedCadence": 1,
                    "GopSize": 90,
                    "Slices": 1,
                    "GopBReference": "DISABLED",
                    "SlowPal": "DISABLED",
                    "SpatialAdaptiveQuantization": "ENABLED",
                    "TemporalAdaptiveQuantization": "ENABLED",
                    "FlickerAdaptiveQuantization": "DISABLED",
                    "EntropyEncoding": "CABAC",
                    "Bitrate": 5000000,
                    "FramerateControl": "INITIALIZE_FROM_SOURCE",
                    "RateControlMode": "CBR",
                    "CodecProfile": "MAIN",
                    "Telecine": "NONE",
                    "MinIInterval": 0,
                    "AdaptiveQuantization": "HIGH",
                    "CodecLevel": "AUTO",
                    "FieldEncoding": "PAFF",
                    "SceneChangeDetect": "ENABLED",
                    "QualityTuningLevel": "SINGLE_PASS",
                    "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                    "UnregisteredSeiTimecode": "DISABLED",
                    "GopSizeUnits": "FRAMES",
                    "ParControl": "INITIALIZE_FROM_SOURCE",
                    "NumberBFramesBetweenReferenceFrames": 2,
                    "RepeatPps": "DISABLED"
                    }
                },
                "AfdSignaling": "NONE",
                "DropFrameTimecode": "ENABLED",
                "RespondToAfd": "NONE",
                "ColorMetadata": "INSERT"
                },
                "AudioDescriptions": [
                {
                    "AudioTypeControl": "FOLLOW_INPUT",
                    "CodecSettings": {
                    "Codec": "AAC",
                    "AacSettings": {
                        "AudioDescriptionBroadcasterMix": "NORMAL",
                        "Bitrate": 96000,
                        "RateControlMode": "CBR",
                        "CodecProfile": "LC",
                        "CodingMode": "CODING_MODE_2_0",
                        "RawFormat": "NONE",
                        "SampleRate": 48000,
                        "Specification": "MPEG4"
                    }
                    },
                    "LanguageCodeControl": "FOLLOW_INPUT"
                }
                ],
                "NameModifier": "_video"
            }
            ],
            "OutputGroupSettings": {
            "Type": "FILE_GROUP_SETTINGS",
            "FileGroupSettings": {
                "Destination": "s3://" + s3_bucket + "/video/" + event_id
            }
            }
        }
        ],
        "AdAvailOffset": 0,
        "Inputs": [
        {
            "InputClippings": [
            {
                "EndTimecode": time_end,
                "StartTimecode": time_start
            }
            ],
            "AudioSelectors": {
            "Audio Selector 1": {
                "Offset": 0,
                "DefaultSelection": "DEFAULT",
                "ProgramSelection": 1
            }
            },
            "VideoSelector": {
            "ColorSpace": "FOLLOW"
            },
            "FilterEnable": "AUTO",
            "PsiControl": "USE_PSI",
            "FilterStrength": 0,
            "DeblockFilter": "DISABLED",
            "DenoiseFilter": "DISABLED",
            "TimecodeSource": "EMBEDDED",
            "FileInput": "s3://" + s3_bucket + "/video/tmp/" + event_id + "/index.m3u8"
        }
        ]
    }
        pprint(jobSettings)
        job = mediaconvert.create_job(Role=EMC_ROLE, UserMetadata=jobMetadata, Settings=jobSettings)
        # pprint(job)

    return 'SUCCESS: it ran'


if __name__ == "__main__":
    XRAY = 'false'
    os.environ['DYNAMO_LIST'] = 'catfinder5000-list'
    os.environ['EMC_ROLE'] = "arn:aws:iam::463540299421:role/vod-MediaConvertIAMRole-1BIVDOODMZT1L-MediaConvertRole"
    os.environ['EMC_ENDPOINT'] = "https://vweb51sm.mediaconvert.us-west-2.amazonaws.com"
    os.environ['S3_BUCKET'] = 'catfinder5000-demo'
    get_environment_variables()

    ### INVOKED from catfinder5001-prekog
    print("getting test data from table: " + str(DYNAMO_LIST))
    table = dynamodb.Table(DYNAMO_LIST)
    response = table.query(
        # IndexName=DYNAMO_LIST_GSI,
        Limit=  1,
        ScanIndexForward=False,
        KeyConditionExpression=Key('label').eq('Cat'),
    )
    # pprint(response['Items'][0])
    event = response['Items'][0]
    event['s3_bucket'] = S3_BUCKET
    # event = {
    #     'event_id': '15132283876b52c212-3ea4-4baa-b018-2bb54aaf0719',
    #     'hls_url': 'https://3ae97e9482b0d011.mediapackage.us-west-2.amazonaws.com/out/v1/3a11c32682a14c7e938962f690510cba/index.m3u8?start=2017-12-14T05:11:25+00:00&end=2017-12-14T05:12:37+00:00',
    #     's3_bucket': 'catfinder5000-demo',
    #     'time_end': '2017-12-14 05:12:37:19',
    #     'time_start': '2017-12-14 05:11:25:29'
    #  }

    ### SNS from MediaConvert
    event_sns = {
        u'account': u'463540299421', 
        u'region': u'us-west-2', 
        u'detail': {
            u'status': u'COMPLETE-TEST', 
            u'outputGroupDetails': [ {u'outputDetails': [ {u'durationInMs': 53500, u'videoDetails': {u'widthInPx': 1280, u'heightInPx': 720 } } ] } ], 
            u'timestamp': 1515538854811, u'jobId': u'1515538821949-ml5i0q', u'queue': u'arn:aws:mediaconvert:us-west-2: 463540299421:queues/Default', 
            u'userMetadata': {
                u'label_sort': u'15209153721e0a850c-70ba-4ebb-9a06-30301ad0b49a', 
                u'label': u'Cat'
            }, 
            u'accountId': u'463540299421' 
        }, 
        u'detail-type': u'MediaConvert Job State Change', u'source': u'aws.mediaconvert', u'version': u'0', u'time': u'2018-01-09T23: 00: 54Z', u'id': u'bd543d7e-0325-76a7-060b-0ee13a931c28', u'resources': [u'arn:aws:mediaconvert:us-west-2: 463540299421:jobs/1515538821949-ml5i0q' ]
    }

    print(lambda_handler(event,None))
    # write scripts for deploy and logs
    with open('deploy', 'w') as outfile:
        outfile.write('lambda-uploader --variables \'{"EMC_ROLE": "' + EMC_ROLE + '","EMC_ENDPOINT": "' + EMC_ENDPOINT + '","DYNAMO_LIST": "' + DYNAMO_LIST + '" }\'')
    with open('logs', 'w') as outfile:
        outfile.write('awslogs get /aws/lambda/catfinder5001-vod ALL --watch')
    