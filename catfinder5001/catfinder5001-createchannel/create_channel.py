#!/usr/bin/env python

"""Creates Channels for MediaLive and MediaPackage

Usage:
    create_channel.py -h | --help
    create_channel.py [--input-id=<inputid>] [--channel-name=<name>] [--no-start] [--no-babysit] [--input-type=<type>] [--HLS-source=<source>] [--role-ARN=<arn>]
    create_channel.py --list-channels
    create_channel.py --stop-channel=<channel_name> [--no-delete]
    create_channel.py --stop-all
    create_channel.py --delete-channel=<channelid>
    create_channel.py --describe-channel=<channelid>
    create_channel.py --start-channel=<channelid> [--no-babysit]

Options:
    -h --help                       Show this screen.
    --input-id=<inputid>            create channel with this input
    --no-start                      don't autostart the channel 
    --channel-name=<name>           create channel with this name ( otherwise its a random )
    --list-channels                 list the channels
    --stop-channel=<channel_name>   stop and delete this channel by name
    --stop-all                      stop all the channels
    --describe-channel=<channelid>  describe this channel id
    --delete-channel=<channelid>    delete this channel id
    --start-channel=<channelid>     start this channel id
    --input-type=<type>             if not using an input-id, specify either RTP, HLS, auto; default is auto which will attempt to use an existing, detached input
    --HLS-source=<source>           if using input type HLS, must provide HLS source URL
    --role-ARN=<arn>                MediaLive role ARN
"""

import boto3
import json
import time
import uuid
import sys
from docopt import docopt
from pprint import pprint
import botocore

## LOOK Here!!! you will need to change this
# MEDIALIVE_ARN = 'arn:aws:iam::1234567890:role/AllowMediaLiveAccessRole' # leah 
MEDIALIVE_ARN = 'arn:aws:iam::1234567890:role/MediaLiveAccessRole' # techmkt
S3_BUCKET = 'nab2018-catfinder5001'
CHANNEL_NAME = 'nab2018-catfinder5001'
REGION = 'us-east-1'
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

ssm = session.client(
    'ssm',
    region_name=REGION,
    )

def param_store_entry_exists(ps_name):
    try:
        response = ssm.get_parameters( 
            Names=[
                ps_name,
            ],
            WithDecryption=False
        )
        if len(response['Parameters']) == 0:
            return False
        else:
            return True
    except Exception, e:
        if 'ParameterAlreadyExists' not in e.message:
            print "Exception raised:", repr(e.message)

def create_param_store_entry(ps_name, ps_value, ps_description='later'):
    try:
        if not param_store_entry_exists(ps_name):
            reponse = ssm.put_parameter(Name=ps_name, Description=ps_description, Value=ps_value, Type='SecureString')
            print "DEBUG: Create Response:", reponse
        else:
            print "Parameter Store entry '{0}' exists".format(ps_name)
            print "implement reveert steps here..."
    except Exception, e:
        if 'ParameterAlreadyExists' in e.message:
            print "Parameter Store entry '{0}' already exists".format(ps_name)
        else:
            print "unknown exception - message", repr(e.message)

def list_inputs():
    inputs = medialive.list_inputs()
    pprint(inputs)

def create_an_input_security_group():
    create_resp = medialive.create_input_security_group(
            WhitelistRules=[{'Cidr': '0.0.0.0/0'}])
    input_security_group_id = create_resp['SecurityGroup']['Id']
    return input_security_group_id

def create_rtp_input(uuid_id, security_group_id):
    create_resp = medialive.create_input(
        Name='input-' + uuid_id, 
        Type='RTP_PUSH', 
        InputSecurityGroups=[security_group_id],
        RequestId=str(time.time())
        )
    pprint(create_resp)
    input_id = create_resp['Input']['Id']
    return input_id

def create_rtmp_input(uuid_id, security_group_id):
    create_resp = medialive.create_input(
        Name='input-' + uuid_id, 
        Type='RTMP_PUSH', 
        Destinations=[
            { 'StreamName': 'live/stream'},
            { 'StreamName': 'live/stream'},
        ],
        InputSecurityGroups=[security_group_id],
        RequestId=str(time.time())
        )
    pprint(create_resp)
    input_id = create_resp['Input']['Id']
    return input_id

def create_hls_input(uuid_id, hls_source):
    create_resp = medialive.create_input(
        Name= uuid_id, 
        Type='URL_PULL', 
        Sources= [
            { 'Url' : hls_source },
            { 'Url' : hls_source }
        ],  
        RequestId=str(time.time())
        )
    print('Input created: {}'.format(create_resp))
    input_id = create_resp['Input']['Id']
    return input_id

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
        print('deleting: {}'.format(this_input['Id']))
        if this_input['State'] == 'DETACHED':
            print('Deleting input {}'.format(this_input['Id']))
            input_resp = medialive.delete_input(InputId=this_input['Id'])

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

def create_a_channel(input_id, channel_name, destinations, s3_bucket):
    channel_resp = medialive.create_channel(
        Name= channel_name,
        RoleArn=MEDIALIVE_ARN,
        InputAttachments = [{
            'InputId': input_id,
            'InputSettings': {
                "SourceEndBehavior": "LOOP",
                'NetworkInputSettings': {
                }
             }
        }],        
        Destinations=[
        {
            "Id": "destination1", 
            "Settings": [
                {
                    "Url": destinations['p_url'], 
                    "Username": destinations['p_u'], 
                    "PasswordParam": destinations['p_u']
                }, 
                {
                    "Url": destinations['b_url'], 
                    "Username": destinations['b_u'], 
                    "PasswordParam": destinations['b_u']
                }
            ]
        }, 
        {
            "Id": "llmq8", 
            "Settings": [
                {
                    "Url": "s3://" + s3_bucket + "/live/stream", 
                    "Username": "", 
                    "PasswordParam": ""
                }, 
                {
                    "Url": "s3://" + s3_bucket + "/live-backup/backup", 
                    "Username": "", 
                    "PasswordParam": ""
                }
            ]
        } ],
        EncoderSettings={
        "TimecodeConfig": {
            "Source": "SYSTEMCLOCK"
        }, 
        "OutputGroups": [
            {
                "OutputGroupSettings": {
                    "HlsGroupSettings": {
                        "TimedMetadataId3Frame": "PRIV", 
                        "CaptionLanguageMappings": [], 
                        "Destination": {
                            "DestinationRefId": "destination1"
                        }, 
                        "IvSource": "FOLLOWS_SEGMENT_NUMBER", 
                        "IndexNSegments": 6, 
                        "InputLossAction": "EMIT_OUTPUT", 
                        "ManifestDurationFormat": "INTEGER", 
                        "CodecSpecification": "RFC_4281", 
                        "IvInManifest": "INCLUDE", 
                        "TimedMetadataId3Period": 10, 
                        "ProgramDateTimePeriod": 600, 
                        "SegmentLength": 2, 
                        "CaptionLanguageSetting": "OMIT", 
                        "ProgramDateTime": "EXCLUDE", 
                        "HlsCdnSettings": {
                            "HlsWebdavSettings": {
                                "NumRetries": 10, 
                                "ConnectionRetryInterval": 1, 
                                "HttpTransferMode": "NON_CHUNKED", 
                                "FilecacheDuration": 300, 
                                "RestartDelay": 15
                            }
                        }, 
                        "TsFileMode": "SEGMENTED_FILES", 
                        "StreamInfResolution": "INCLUDE", 
                        "ClientCache": "ENABLED", 
                        "AdMarkers": [
                            "ELEMENTAL_SCTE35"
                        ], 
                        "KeepSegments": 360, 
                        "SegmentationMode": "USE_SEGMENT_DURATION", 
                        "OutputSelection": "MANIFESTS_AND_SEGMENTS", 
                        "ManifestCompression": "NONE", 
                        "DirectoryStructure": "SINGLE_DIRECTORY", 
                        "Mode": "LIVE"
                    }
                }, 
                "Outputs": [
                    {
                        "VideoDescriptionName": "video_1080p30", 
                        "AudioDescriptionNames": [
                            "audio_1"
                        ], 
                        "CaptionDescriptionNames": [], 
                        "OutputSettings": {
                            "HlsOutputSettings": {
                                "NameModifier": "_1080p30", 
                                "HlsSettings": {
                                    "StandardHlsSettings": {
                                        "M3u8Settings": {
                                            "PcrControl": "PCR_EVERY_PES_PACKET", 
                                            "TimedMetadataBehavior": "NO_PASSTHROUGH", 
                                            "PmtPid": "480", 
                                            "Scte35Pid": "500", 
                                            "VideoPid": "481", 
                                            "ProgramNum": 1, 
                                            "AudioPids": "492-498", 
                                            "AudioFramesPerPes": 4, 
                                            "EcmPid": "8182", 
                                            "Scte35Behavior": "PASSTHROUGH"
                                        }, 
                                        "AudioRenditionSets": "PROGRAM_AUDIO"
                                    }
                                }
                            }
                        }
                    }, 
                    {
                        "VideoDescriptionName": "video_720p30", 
                        "AudioDescriptionNames": [
                            "audio_2"
                        ], 
                        "CaptionDescriptionNames": [], 
                        "OutputSettings": {
                            "HlsOutputSettings": {
                                "NameModifier": "_720p30", 
                                "HlsSettings": {
                                    "StandardHlsSettings": {
                                        "M3u8Settings": {
                                            "PcrControl": "PCR_EVERY_PES_PACKET", 
                                            "TimedMetadataBehavior": "NO_PASSTHROUGH", 
                                            "PmtPid": "480", 
                                            "Scte35Pid": "500", 
                                            "VideoPid": "481", 
                                            "ProgramNum": 1, 
                                            "AudioPids": "492-498", 
                                            "AudioFramesPerPes": 4, 
                                            "EcmPid": "8182", 
                                            "Scte35Behavior": "PASSTHROUGH"
                                        }, 
                                        "AudioRenditionSets": "PROGRAM_AUDIO"
                                    }
                                }
                            }
                        }
                    }, 
                    {
                        "VideoDescriptionName": "video_480p30", 
                        "AudioDescriptionNames": [
                            "audio_za9dzo"
                        ], 
                        "CaptionDescriptionNames": [], 
                        "OutputSettings": {
                            "HlsOutputSettings": {
                                "NameModifier": "_480p30", 
                                "HlsSettings": {
                                    "StandardHlsSettings": {
                                        "M3u8Settings": {
                                            "PcrControl": "PCR_EVERY_PES_PACKET", 
                                            "TimedMetadataBehavior": "NO_PASSTHROUGH", 
                                            "PmtPid": "480", 
                                            "Scte35Pid": "500", 
                                            "VideoPid": "481", 
                                            "ProgramNum": 1, 
                                            "AudioPids": "492-498", 
                                            "AudioFramesPerPes": 4, 
                                            "EcmPid": "8182", 
                                            "Scte35Behavior": "PASSTHROUGH"
                                        }, 
                                        "AudioRenditionSets": "PROGRAM_AUDIO"
                                    }
                                }
                            }
                        }
                    }, 
                    {
                        "VideoDescriptionName": "video_240p30", 
                        "AudioDescriptionNames": [
                            "audio_40bxb2"
                        ], 
                        "CaptionDescriptionNames": [], 
                        "OutputSettings": {
                            "HlsOutputSettings": {
                                "NameModifier": "_270p30", 
                                "HlsSettings": {
                                    "StandardHlsSettings": {
                                        "M3u8Settings": {
                                            "PcrControl": "PCR_EVERY_PES_PACKET", 
                                            "TimedMetadataBehavior": "NO_PASSTHROUGH", 
                                            "PmtPid": "480", 
                                            "Scte35Pid": "500", 
                                            "VideoPid": "481", 
                                            "ProgramNum": 1, 
                                            "AudioPids": "492-498", 
                                            "AudioFramesPerPes": 4, 
                                            "EcmPid": "8182", 
                                            "Scte35Behavior": "PASSTHROUGH"
                                        }, 
                                        "AudioRenditionSets": "PROGRAM_AUDIO"
                                    }
                                }
                            }
                        }
                    }
                ], 
                "Name": "MediaPackage"
            }, 
            {
                "OutputGroupSettings": {
                    "HlsGroupSettings": {
                        "TimedMetadataId3Frame": "PRIV", 
                        "CaptionLanguageMappings": [], 
                        "Destination": {
                            "DestinationRefId": "llmq8"
                        }, 
                        "IvSource": "FOLLOWS_SEGMENT_NUMBER", 
                        "IndexNSegments": 7, 
                        "InputLossAction": "EMIT_OUTPUT", 
                        "ManifestDurationFormat": "FLOATING_POINT", 
                        "CodecSpecification": "RFC_4281", 
                        "IvInManifest": "INCLUDE", 
                        "TimedMetadataId3Period": 10, 
                        "ProgramDateTimePeriod": 10, 
                        "SegmentLength": 10, 
                        "CaptionLanguageSetting": "OMIT", 
                        "ProgramDateTime": "INCLUDE", 
                        "Mode": "LIVE", 
                        "TsFileMode": "SEGMENTED_FILES", 
                        "StreamInfResolution": "INCLUDE", 
                        "ClientCache": "ENABLED", 
                        "AdMarkers": [], 
                        "KeepSegments": 40, 
                        "SegmentationMode": "USE_SEGMENT_DURATION", 
                        "OutputSelection": "MANIFESTS_AND_SEGMENTS", 
                        "ManifestCompression": "NONE", 
                        "DirectoryStructure": "SINGLE_DIRECTORY"
                    }
                }, 
                "Outputs": [
                    {
                        "OutputName": "vf6z8", 
                        "AudioDescriptionNames": [
                            "audio_f42hdc"
                        ], 
                        "CaptionDescriptionNames": [], 
                        "VideoDescriptionName": "video_tikzx7", 
                        "OutputSettings": {
                            "HlsOutputSettings": {
                                "SegmentModifier": "$dt$", 
                                "NameModifier": "_1", 
                                "HlsSettings": {
                                    "StandardHlsSettings": {
                                        "M3u8Settings": {
                                            "PcrControl": "PCR_EVERY_PES_PACKET", 
                                            "TimedMetadataBehavior": "NO_PASSTHROUGH", 
                                            "PmtPid": "480", 
                                            "Scte35Pid": "500", 
                                            "VideoPid": "481", 
                                            "ProgramNum": 1, 
                                            "AudioPids": "492-498", 
                                            "AudioFramesPerPes": 4, 
                                            "EcmPid": "8182", 
                                            "Scte35Behavior": "NO_PASSTHROUGH"
                                        }, 
                                        "AudioRenditionSets": "PROGRAM_AUDIO"
                                    }
                                }
                            }
                        }
                    }
                ], 
                "Name": "S3 Bucket"
            }
        ], 
        "GlobalConfiguration": {
            "SupportLowFramerateInputs": "DISABLED", 
            "OutputTimingSource": "SYSTEM_CLOCK", 
            "InputEndAction": "SWITCH_AND_LOOP_INPUTS"
        }, 
        "CaptionDescriptions": [], 
        "VideoDescriptions": [
            {
                "CodecSettings": {
                    "H264Settings": {
                        "Syntax": "DEFAULT", 
                        "FramerateNumerator": 30000, 
                        "Profile": "HIGH", 
                        "GopSize": 2, 
                        "AfdSignaling": "NONE", 
                        "FramerateControl": "SPECIFIED", 
                        "ColorMetadata": "INSERT", 
                        "FlickerAq": "ENABLED", 
                        "LookAheadRateControl": "HIGH", 
                        "FramerateDenominator": 1001, 
                        "Bitrate": 5000000, 
                        "TimecodeInsertion": "PIC_TIMING_SEI", 
                        "NumRefFrames": 3, 
                        "EntropyEncoding": "CABAC", 
                        "GopSizeUnits": "SECONDS", 
                        "Level": "H264_LEVEL_AUTO", 
                        "GopBReference": "ENABLED", 
                        "AdaptiveQuantization": "HIGH", 
                        "GopNumBFrames": 3, 
                        "ScanType": "PROGRESSIVE", 
                        "ParControl": "INITIALIZE_FROM_SOURCE", 
                        "Slices": 1, 
                        "SpatialAq": "ENABLED", 
                        "TemporalAq": "ENABLED", 
                        "RateControlMode": "CBR", 
                        "SceneChangeDetect": "ENABLED", 
                        "GopClosedCadence": 1
                    }
                }, 
                "Name": "video_1080p30", 
                "Sharpness": 50, 
                "Height": 1080, 
                "Width": 1920, 
                "ScalingBehavior": "DEFAULT", 
                "RespondToAfd": "NONE"
            }, 
            {
                "CodecSettings": {
                    "H264Settings": {
                        "Syntax": "DEFAULT", 
                        "FramerateNumerator": 30000, 
                        "Profile": "HIGH", 
                        "GopSize": 2, 
                        "AfdSignaling": "NONE", 
                        "FramerateControl": "SPECIFIED", 
                        "ColorMetadata": "INSERT", 
                        "FlickerAq": "ENABLED", 
                        "LookAheadRateControl": "HIGH", 
                        "FramerateDenominator": 1001, 
                        "Bitrate": 3000000, 
                        "TimecodeInsertion": "PIC_TIMING_SEI", 
                        "NumRefFrames": 3, 
                        "EntropyEncoding": "CABAC", 
                        "GopSizeUnits": "SECONDS", 
                        "Level": "H264_LEVEL_AUTO", 
                        "GopBReference": "ENABLED", 
                        "AdaptiveQuantization": "HIGH", 
                        "GopNumBFrames": 3, 
                        "ScanType": "PROGRESSIVE", 
                        "ParControl": "INITIALIZE_FROM_SOURCE", 
                        "Slices": 1, 
                        "SpatialAq": "ENABLED", 
                        "TemporalAq": "ENABLED", 
                        "RateControlMode": "CBR", 
                        "SceneChangeDetect": "ENABLED", 
                        "GopClosedCadence": 1
                    }
                }, 
                "Name": "video_720p30", 
                "Sharpness": 100, 
                "Height": 720, 
                "Width": 1280, 
                "ScalingBehavior": "DEFAULT", 
                "RespondToAfd": "NONE"
            }, 
            {
                "CodecSettings": {
                    "H264Settings": {
                        "Syntax": "DEFAULT", 
                        "FramerateNumerator": 30000, 
                        "Profile": "MAIN", 
                        "GopSize": 2, 
                        "AfdSignaling": "NONE", 
                        "FramerateControl": "SPECIFIED", 
                        "ColorMetadata": "INSERT", 
                        "FlickerAq": "ENABLED", 
                        "LookAheadRateControl": "HIGH", 
                        "FramerateDenominator": 1001, 
                        "Bitrate": 1500000, 
                        "TimecodeInsertion": "PIC_TIMING_SEI", 
                        "NumRefFrames": 3, 
                        "EntropyEncoding": "CABAC", 
                        "GopSizeUnits": "SECONDS", 
                        "Level": "H264_LEVEL_AUTO", 
                        "GopBReference": "ENABLED", 
                        "AdaptiveQuantization": "HIGH", 
                        "GopNumBFrames": 3, 
                        "ScanType": "PROGRESSIVE", 
                        "ParControl": "INITIALIZE_FROM_SOURCE", 
                        "Slices": 1, 
                        "SpatialAq": "ENABLED", 
                        "TemporalAq": "ENABLED", 
                        "RateControlMode": "CBR", 
                        "SceneChangeDetect": "ENABLED", 
                        "GopClosedCadence": 1
                    }
                }, 
                "Name": "video_480p30", 
                "Sharpness": 100, 
                "Height": 480, 
                "Width": 854, 
                "ScalingBehavior": "STRETCH_TO_OUTPUT", 
                "RespondToAfd": "NONE"
            }, 
            {
                "CodecSettings": {
                    "H264Settings": {
                        "Syntax": "DEFAULT", 
                        "FramerateNumerator": 30000, 
                        "Profile": "MAIN", 
                        "GopSize": 2, 
                        "AfdSignaling": "NONE", 
                        "FramerateControl": "SPECIFIED", 
                        "ColorMetadata": "INSERT", 
                        "FlickerAq": "ENABLED", 
                        "LookAheadRateControl": "HIGH", 
                        "FramerateDenominator": 1001, 
                        "Bitrate": 750000, 
                        "TimecodeInsertion": "PIC_TIMING_SEI", 
                        "NumRefFrames": 3, 
                        "EntropyEncoding": "CABAC", 
                        "GopSizeUnits": "SECONDS", 
                        "Level": "H264_LEVEL_AUTO", 
                        "GopBReference": "ENABLED", 
                        "AdaptiveQuantization": "HIGH", 
                        "GopNumBFrames": 3, 
                        "ScanType": "PROGRESSIVE", 
                        "ParControl": "INITIALIZE_FROM_SOURCE", 
                        "Slices": 1, 
                        "SpatialAq": "ENABLED", 
                        "TemporalAq": "ENABLED", 
                        "RateControlMode": "CBR", 
                        "SceneChangeDetect": "ENABLED", 
                        "GopClosedCadence": 1
                    }
                }, 
                "Name": "video_240p30", 
                "Sharpness": 100, 
                "Height": 270, 
                "Width": 480, 
                "ScalingBehavior": "STRETCH_TO_OUTPUT", 
                "RespondToAfd": "NONE"
            }, 
            {
                "CodecSettings": {
                    "H264Settings": {
                        "Syntax": "DEFAULT", 
                        "Profile": "MAIN", 
                        "GopSize": 2, 
                        "AfdSignaling": "NONE", 
                        "FramerateControl": "SPECIFIED", 
                        "FramerateNumerator": 30000, 
                        "FramerateDenominator": 1001,
                        "ColorMetadata": "INSERT", 
                        "FlickerAq": "ENABLED", 
                        "LookAheadRateControl": "MEDIUM", 
                        "Bitrate": 2000000, 
                        "TimecodeInsertion": "PIC_TIMING_SEI", 
                        "NumRefFrames": 1, 
                        "EntropyEncoding": "CABAC", 
                        "GopSizeUnits": "SECONDS", 
                        "Level": "H264_LEVEL_AUTO", 
                        "GopBReference": "DISABLED", 
                        "AdaptiveQuantization": "MEDIUM", 
                        "GopNumBFrames": 0, 
                        "ScanType": "PROGRESSIVE", 
                        "ParControl": "INITIALIZE_FROM_SOURCE", 
                        "SpatialAq": "ENABLED", 
                        "TemporalAq": "ENABLED", 
                        "RateControlMode": "CBR", 
                        "SceneChangeDetect": "ENABLED", 
                        "GopClosedCadence": 1
                    }
                }, 
                "Name": "video_tikzx7", 
                "Sharpness": 50, 
                "Height": 540, 
                "Width": 960, 
                "ScalingBehavior": "DEFAULT", 
                "RespondToAfd": "NONE"
            }
        ], 
        "AudioDescriptions": [
            {
                "CodecSettings": {
                    "AacSettings": {
                        "Profile": "LC", 
                        "InputType": "NORMAL", 
                        "RateControlMode": "CBR", 
                        "Spec": "MPEG4", 
                        "SampleRate": 48000, 
                        "Bitrate": 128000, 
                        "CodingMode": "CODING_MODE_2_0", 
                        "RawFormat": "NONE"
                    }
                }, 
                "LanguageCode": "eng", 
                "AudioSelectorName": "Default", 
                "LanguageCodeControl": "USE_CONFIGURED", 
                "AudioTypeControl": "USE_CONFIGURED", 
                "AudioType": "UNDEFINED", 
                "Name": "audio_1"
            }, 
            {
                "CodecSettings": {
                    "AacSettings": {
                        "Profile": "LC", 
                        "InputType": "NORMAL", 
                        "RateControlMode": "CBR", 
                        "Spec": "MPEG4", 
                        "SampleRate": 48000, 
                        "Bitrate": 128000, 
                        "CodingMode": "CODING_MODE_2_0", 
                        "RawFormat": "NONE"
                    }
                }, 
                "LanguageCode": "eng", 
                "Name": "audio_2", 
                "LanguageCodeControl": "USE_CONFIGURED", 
                "AudioTypeControl": "USE_CONFIGURED", 
                "AudioType": "UNDEFINED"
            }, 
            {
                "CodecSettings": {
                    "AacSettings": {
                        "Profile": "LC", 
                        "InputType": "NORMAL", 
                        "RateControlMode": "CBR", 
                        "Spec": "MPEG4", 
                        "SampleRate": 48000, 
                        "Bitrate": 192000, 
                        "CodingMode": "CODING_MODE_2_0", 
                        "RawFormat": "NONE"
                    }
                }, 
                "LanguageCode": "eng", 
                "Name": "audio_za9dzo", 
                "LanguageCodeControl": "USE_CONFIGURED", 
                "AudioTypeControl": "USE_CONFIGURED", 
                "AudioType": "UNDEFINED"
            }, 
            {
                "CodecSettings": {
                    "AacSettings": {
                        "Profile": "LC", 
                        "InputType": "NORMAL", 
                        "RateControlMode": "CBR", 
                        "Spec": "MPEG4", 
                        "SampleRate": 48000, 
                        "Bitrate": 192000, 
                        "CodingMode": "CODING_MODE_2_0", 
                        "RawFormat": "NONE"
                    }
                }, 
                "LanguageCode": "eng", 
                "Name": "audio_40bxb2", 
                "LanguageCodeControl": "USE_CONFIGURED", 
                "AudioTypeControl": "USE_CONFIGURED", 
                "AudioType": "UNDEFINED"
            }, 
            {
                "CodecSettings": {
                    "AacSettings": {
                        "Profile": "LC", 
                        "InputType": "NORMAL", 
                        "RateControlMode": "CBR", 
                        "Spec": "MPEG4", 
                        "SampleRate": 48000, 
                        "Bitrate": 192000, 
                        "CodingMode": "CODING_MODE_2_0", 
                        "RawFormat": "NONE"
                    }
                }, 
                "LanguageCodeControl": "FOLLOW_INPUT", 
                "AudioTypeControl": "FOLLOW_INPUT", 
                "Name": "audio_f42hdc"
            }
        ]
    }
    )
    print('Channel created: {}'.format(channel_resp))
    channel_id = channel_resp['Channel']['Id']
    return channel_id

def start_a_channel(channel_id):
    print('Starting channel {}'.format(channel_id))
    channel_resp = medialive.start_channel(ChannelId=channel_id)
    print('Channel Started: {}'.format(channel_resp))

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
        if endpoint['Id'] == channel_name + '-p_endpoint':
            resp = mediapackage.delete_origin_endpoint(Id = endpoint['Id'])
            print('enpoint-a deleted: {}'.format(resp))
            endpoint_count += 1
        if endpoint['Id'] == channel_name + '-b_endpoint':
            resp = mediapackage.delete_origin_endpoint(Id = endpoint['Id'])
            print('enpoint-b deleted: {}'.format(resp))
            endpoint_count += 1            
    
    # Delete Channels
    channel_count = 0
    channels_listing = mediapackage.list_channels()
    for channel in channels_listing['Channels']:
        if channel['Id'] == channel_name + '-p':
            resp = mediapackage.delete_channel(Id = channel['Id'])    
            print('channel-p deleted: {}'.format(resp))
            channel_count += 1            
        if channel['Id'] == channel_name + '-b':
            resp = mediapackage.delete_channel(Id = channel['Id'])    
            print('channel-b deleted: {}'.format(resp))
            channel_count += 1            
    print('Mediapackage Channels Deleted: {} Endpoints Deleted: {}'.format(channel_count,endpoint_count))            
            

def get_an_input_url(input_id):
    print('Getting input {}'.format(input_id))
    input_resp = medialive.get_input(InputId=input_id)
    pprint(input_resp['Input']['Endpoints'])

def get_an_input(input_id):
    print('Getting input {}'.format(input_id))
    input_resp = medialive.get_input(InputId=input_id)
    pprint(input_resp)

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
 
def start_and_wait_for_channel(channel_id):
    start_a_channel(channel_id)
    final_state = wait_for_channel(channel_id, states=['RUNNING'], timeout_secs=240)
    return final_state
 
def stop_and_wait_for_channel(channel_id):
    stop_a_channel(channel_id)
    final_state = wait_for_channel(channel_id, states=['IDLE'], timeout_secs=120)
    return final_state
 
def wait_for_no_channel(channel_id, timeout_secs):
    start_time = time.time()
    timeout_millis = timeout_secs * 1000
    try:
        while time.time() - start_time <= timeout_millis:
            describe_a_channel(channel_id)
            time.sleep(3)
    except botocore.exceptions.ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            return
 
def delete_and_wait_for_channel(channel_id):
    delete_a_channel(channel_id)
    # wait_for_no_channel(channel_id, timeout_secs=60)

def get_avail_input():
    inputs = medialive.list_inputs()
    # pprint(inputs)
    last_input = { 'id': 'none', 'name': 'none'}
    for this_input in inputs['Inputs']:
        # print('{} \t{} \t{}'.format(this_input['Id'], this_input['State'], this_input['Name']))
        if this_input['State'] == 'DETACHED':
            last_input = { 'id': this_input['Id'], 'name': this_input['Name']}
    return last_input

def create_mediapackage_channel(channel_name):
    channel_p_name = channel_name + "-p"
    channel_b_name = channel_name + "-b"
    newchannel = mediapackage.create_channel(
        Id=channel_p_name, 
        Description="primary channel created by leahware"
        )
    print("Mediapackage primary channel: {}".format(newchannel))

    newchannel = mediapackage.create_channel(
        Id=channel_b_name, 
        Description="backup channel created by leahware"
        )
    print("Mediapackage backup channel: {}".format(newchannel))

    babel_p = mediapackage.describe_channel(Id=channel_p_name)
    babel_b = mediapackage.describe_channel(Id=channel_b_name)
    destinations = {
        'p_id' : channel_p_name, 'p_url' : babel_p['HlsIngest']['IngestEndpoints'][0]['Url'], 'p_u' : babel_p['HlsIngest']['IngestEndpoints'][0]['Username'], 'p_p' : babel_p['HlsIngest']['IngestEndpoints'][0]['Password'],
        'b_id' : channel_b_name, 'b_url' : babel_b['HlsIngest']['IngestEndpoints'][0]['Url'], 'b_u' : babel_b['HlsIngest']['IngestEndpoints'][0]['Username'], 'b_p' : babel_b['HlsIngest']['IngestEndpoints'][0]['Password'],
    }
    return destinations

def create_mediapackage_endpoints(destinations):
    startover_window = 259198
    segment_duration = 10
    playlist_window = 60
    newendpoint_p = mediapackage.create_origin_endpoint(
        Id=destinations['p_id'] + "_endpoint",
        ChannelId=destinations['p_id'],
        Description="primary endpoint created by leahware",
        ManifestName="index",
        StartoverWindowSeconds=startover_window,
        HlsPackage={
            "SegmentDurationSeconds": segment_duration,
            "PlaylistWindowSeconds": playlist_window,
            "PlaylistType": "event",
            "AdMarkers": "SCTE35_ENHANCED",
            "IncludeIframeOnlyStream": False,
            "UseAudioRenditionGroup": False,
            "StreamSelection": {
                "StreamOrder": "original"
            }
        }
    )
    print('Mediapackage endpoint: {}'.format(newendpoint_p['Url']))

    newendpoint_b = mediapackage.create_origin_endpoint(
        Id=destinations['b_id'] + "_endpoint",
        ChannelId=destinations['b_id'],
        Description="backup endpoint created by leahware",
        ManifestName="index",
        StartoverWindowSeconds=startover_window,
        HlsPackage={
            "SegmentDurationSeconds": segment_duration,
            "PlaylistWindowSeconds": playlist_window,
            "PlaylistType": "event",
            "AdMarkers": "SCTE35_ENHANCED",
            "IncludeIframeOnlyStream": False,
            "UseAudioRenditionGroup": False,
            "StreamSelection": {
                "StreamOrder": "original"
            }
        }
    )
    print('Mediapackage endpoint: {}'.format(newendpoint_b['Url']))

if __name__ == '__main__':
    args = docopt(__doc__, version='0.1')
    
    if args['--stop-all']:
        delete_all_the_channels()
        delete_all_the_inputs()
        delete_all_the_mediapackage()
        sys.exit(1)    

    if args['--describe-channel']:
        describe_a_channel_details(args['--describe-channel'])
        sys.exit(1)    
    
    if args['--delete-channel']:
        delete_and_wait_for_channel(args['--delete-channel'])
        sys.exit(1)    
    
    if args['--start-channel']:
        start_a_channel(args['--start-channel'])
        if not args['--no-babysit']:
            final_state = start_and_wait_for_channel(args['--start-channel'])
            if final_state == 'RUNNING':
                print('Channel is running!')    
        else:
            print('Channel was started and not monitored...')
        sys.exit(1)         
    
    if args['--stop-channel']:
        channel_name = args['--stop-channel']
        channel_id = 0
        token = ''
        channels = []
        with _timeout(None):
            while True:
                chan = medialive.list_channels(NextToken=token)
                token = chan.get('NextToken', '')
                channels.extend(chan['Channels'])
                if token == '': break    
        for ch in channels:
            if ch['Name'] == channel_name: 
                channel_id = ch['Id']
                input_id = ch['InputAttachments'][0]['InputId']
        if channel_id == 0: 
            print('Channel does not exist')
            print('Lets doublecheck for MediaPackage stuff...')
            delete_a_mediapackage_channel(channel_name)
            sys.exit(1)
        else:
            print('MediaLive Channel Id: {} found for Channel Name: {}'.format(channel_id, channel_name))
            final_state = stop_and_wait_for_channel(channel_id)
            if(final_state == 'IDLE'):
                if not args['--no-delete']:
                    delete_a_mediapackage_channel(channel_name)
                    delete_and_wait_for_channel(channel_id)
                    time.sleep(3)
                    delete_an_input(input_id)
                    print('woomy!')
            else:
                print('Channel {} did not stop correctly :/ '.format(args['--stop-channel']))
            sys.exit(1)        
    
    if args['--list-channels']:
        list_channels()
        sys.exit(1)    
    
    if not args['--input-id']:
        input_name = CHANNEL_NAME
        #if input type is not provided at all or  HLS , then create a new input        
        if not args['--input-type'] or args['--input-type']=='HLS':
            hls_source = 'https://techmkt-videoarchive.s3.amazonaws.com/1080p30/adkitten/stream.m3u8'
            if not args['--HLS-source']:
                print('HLS source not given... using canned content')
            else:
                hls_source = args['--HLS-source']
            print('Creating HLS input url: {}'.format(hls_source))
            input_id=create_hls_input(input_name, hls_source)
        #if it's auto, try to pick an available, detached input
        elif args['--input-type']=="auto":
            this_input = get_avail_input()
            print('Grabbed existing detached input: {}'.format(this_input['name']))
            if this_input['id'] == 'none':
                print('No Inputs were available. Rerun script and specify what input type you want created')
                sys.exit(1)
            else:
                channel_name = str(this_input['name'])
                input_id = this_input['id']
        #if RTMP, create a new input
        elif args['--input-type']=='RTMP':
                print('Creating RTMP input')
                sec_group_id = create_an_input_security_group()
                input_id = create_rtmp_input(input_name, sec_group_id)
                
        #if RTP, create a new input
        elif args['--input-type']=='RTP':
                print('Creating RTP input')
                sec_group_id = create_an_input_security_group()
                input_id = create_rtp_input(input_name, sec_group_id)
    else:
        input_id = args['--input-id']   
    
    if not args['--channel-name']:
        # channel_name = CHANNEL_NAME + str(uuid.uuid4())
        channel_name = CHANNEL_NAME
    else:
        channel_name = args['--channel-name']

    if args['--role-ARN']:
        MEDIALIVE_ARN = args['--role-ARN']
        print(MEDIALIVE_ARN)
        sys.exit(1)
    destinations = create_mediapackage_channel(channel_name)
    create_param_store_entry(destinations['p_u'], destinations['p_p'], destinations['p_url'])
    create_param_store_entry(destinations['b_u'], destinations['b_p'], destinations['b_url'])
    channel_id = create_a_channel(input_id, channel_name, destinations, S3_BUCKET)
    print('Channel id is: {} for channel name: {} '.format(channel_id, channel_name))
    if not args['--no-start']:
        print('Waiting for channel to become IDLE')
        final_state = wait_for_channel(channel_id, ['CREATE_FAILED', 'IDLE'], timeout_secs=60)
        print('Channel {} is in {} state'.format(channel_id, final_state))
        if final_state == 'IDLE':
            start_a_channel(channel_id)
            if not args['--no-babysit']:
                final_state = start_and_wait_for_channel(channel_id)
                if final_state == 'RUNNING':
                    print('Channel is running!')
                    create_mediapackage_endpoints(destinations)
            else:
                print('Channel was started and not monitored...')
                create_mediapackage_endpoints(destinations)
    else:
        print('Channel was created and not started...')
        create_mediapackage_endpoints(destinations)
     