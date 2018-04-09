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
import datetime

# patch_all()
XRAY = 'true'

## these are unique and must be set
S3_BUCKET = "not-set"

## hardcoded for console use
DYNAMO_MAIN = "catfinder5002-main"
DYNAMO_MAIN_GSI = "id_type-id_filename-index"


FFPROBE = './ffprobe'
FFMPEG = './ffmpeg'
SOX = './sox'

s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb')
transcribe = boto3.client('transcribe', region_name='us-east-1')
translate = boto3.client('translate')
comprehend = boto3.client('comprehend')

def get_environment_variables():
    global S3_BUCKET
    global DYNAMO_MAIN

    if os.environ.get('S3_BUCKET') is not None:
        S3_BUCKET = os.environ['S3_BUCKET']
        print('environment variable S3_BUCKET was found: {}'.format(S3_BUCKET))
    if os.environ.get('DYNAMO_MAIN') is not None:
        DYNAMO_MAIN = os.environ['DYNAMO_MAIN']
        print('environment variable DYNAMO_MAIN was found: {}'.format(DYNAMO_MAIN))

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

def update_dyanmo_main ( dynamo_object ):
    ## DynamoDB Update
    print("put_dynamo to table: " + str(DYNAMO_MAIN))
    table = dynamodb.Table(DYNAMO_MAIN)
    response = table.update_item(
        Key={
            'id_filename': dynamo_object['id_filename'],
        },
        UpdateExpression="set timestamp_updated = :timestamp_updated, transcribe_status = :transcribe_status, transcribe_transcript = :transcribe_transcript  ",
        ExpressionAttributeValues={
                ':timestamp_updated': int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds()),
                ':transcribe_status': dynamo_object['transcribe_status'],
                ':transcribe_transcript': dynamo_object['transcribe_transcript'],
        },
        ReturnValues="UPDATED_NEW"
    )
    # print("dynamo update_item succeeded: {}".format(response))
    print("dynamo update_item succeeded")
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

def strip (data):
    if not isinstance(data, dict) and not isinstance(data, list) and not isinstance(data, str) and not isinstance(data, unicode):
        return False
    return len(data) == 0
def stripper (data):
    if isinstance(data, dict):
        return {k: stripper(v) for k, v in data.iteritems() if not strip(v)}
    elif isinstance(data, list):
        return [stripper(v) for v in data if not strip(v)]
    return data

def write_json():

    ## set tmp directory
    tmpdir = '/tmp/' + str(uuid.uuid4()) + '/'
    ensure_dir(tmpdir)

    rekog_type = 'minute'
    print("query of table: " + str(DYNAMO_MAIN))
    table = dynamodb.Table(DYNAMO_MAIN)    
    response = table.query(
        Limit=45,
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

def lambda_handler(event, context):
    if XRAY == 'true':
        patch_all()    
    get_environment_variables()  
    print('S3_BUCKET: {}'.format(S3_BUCKET))
    master_ttl = 3600

    ##### Transcribe Status updates
    print("query of table: " + str(DYNAMO_MAIN))
    table = dynamodb.Table(DYNAMO_MAIN)    
    response = table.query(
        Limit=10,
        IndexName=DYNAMO_MAIN_GSI,        
        ScanIndexForward=False,
        KeyConditionExpression=Key('id_type').eq('minute'),
    )
    for item in response['Items']:
        # print('dynamo transcribe_status status: {} \t transcribe_transcript: {}'.format(item['transcribe_status'], item['transcribe_transcript']))
        if item['transcribe_status'] == 'IN_PROGRESS':
            transcribe_job = transcribe.get_transcription_job(TranscriptionJobName=item['transcribe_job'])
            print('transcribe status: {}'.format(transcribe_job['TranscriptionJob']['TranscriptionJobStatus']))            
            transcribe_status = transcribe_job['TranscriptionJob']['TranscriptionJobStatus']
            update_dyanmo_main( {'id_filename' : item['id_filename'], 'transcribe_status' : transcribe_status, 'transcribe_transcript' : 'IN_PROGRESS' } )

        # if item['transcribe_status'] == 'COMPLETED' and item['transcribe_transcript'] == 'IN_PROGRESS':
        if item['transcribe_status'] == 'COMPLETED':
            if item['transcribe_transcript'] == 'IN_PROGRESS':
                print('{} needs to be updated dynamo \t transcribe_status status: {} \t transcribe_transcript: {}'.format(item['id_filename'], item['transcribe_status'], item['transcribe_transcript']))
                transcribe_job = transcribe.get_transcription_job(TranscriptionJobName=item['transcribe_job'])
                # print('transcribe_transcript_uri: {}'.format(transcribe_job['TranscriptionJob']['Transcript']['TranscriptFileUri']))            
                transcribe_status = transcribe_job['TranscriptionJob']['TranscriptionJobStatus']
                transcribe_transcript_uri = transcribe_job['TranscriptionJob']['Transcript']['TranscriptFileUri']
                transcribe_transcript_string = get_url(transcribe_transcript_uri)
                transcribe_transcript_dict = json.loads(transcribe_transcript_string)
                transcribe_transcript_dirty = transcribe_transcript_dict['results']
                # print('transcribe_transcript_dirty: {}'.format(transcribe_transcript_dirty))
                transcribe_transcript = stripper(transcribe_transcript_dirty)
                # print('transcribe_transcript: {}'.format(transcribe_transcript))
                datetime_start = datetime.datetime.strptime(item['timestamp_start'], '%Y-%m-%dT%H:%M:%S.%fZ')
                ## SENTENCES
                if 'transcripts' in transcribe_transcript:
                    comprehend_dict = {}
                    for transcripts in transcribe_transcript['transcripts']:
                        if 'transcript' in transcripts:
                            transcript = transcripts['transcript']
                            transcript = unicode(transcript.encode("utf-8")[:999], "utf-8", errors="ignore")
                            source_lang = 'en'
                            detect_dominant_language = comprehend.detect_dominant_language(Text=transcript)['Languages'][0]
                            detect_dominant_language['Score'] = str(detect_dominant_language['Score'])
                            comprehend_dict['detect_dominant_language'] = detect_dominant_language
                            source_lang = detect_dominant_language['LanguageCode']
                            # key_phrases
                            key_phrases = comprehend.detect_key_phrases(Text=transcript,LanguageCode=source_lang)['KeyPhrases']
                            for key_phrase in key_phrases:
                                key_phrase['Score'] = str(key_phrase['Score'])
                            comprehend_dict['key_phrases'] = key_phrases
                            # sentiment
                            detect_sentiment = comprehend.detect_sentiment(Text=transcript,LanguageCode=source_lang)
                            comprehend_dict['sentiment'] = detect_sentiment['Sentiment']
                            for key,value in detect_sentiment['SentimentScore'].iteritems():
                                detect_sentiment['SentimentScore'][key] = str(value)
                            comprehend_dict['sentiment_score'] = detect_sentiment['SentimentScore']        
                            # detect_entities
                            detect_entities = comprehend.detect_entities(Text=transcript,LanguageCode=source_lang)['Entities']
                            for detect_entity in detect_entities:
                                detect_entity['Score'] = str(detect_entity['Score'])
                            comprehend_dict['detect_entities'] = detect_entities                   
                            transcripts['comprehend'] = comprehend_dict
                            ## translate
                            transcripts[source_lang] = transcript
                            target_lang = 'ar'
                            transcripts[target_lang] = translate.translate_text(Text=transcript, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)['TranslatedText']
                            target_lang = 'zh'
                            transcripts[target_lang] = translate.translate_text(Text=transcript, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)['TranslatedText']
                            target_lang = 'fr'
                            transcripts[target_lang] = translate.translate_text(Text=transcript, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)['TranslatedText']
                            target_lang = 'de'
                            transcripts[target_lang] = translate.translate_text(Text=transcript, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)['TranslatedText']
                            target_lang = 'pt'
                            transcripts[target_lang] = translate.translate_text(Text=transcript, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)['TranslatedText']
                            target_lang = 'es'
                            transcripts[target_lang] = translate.translate_text(Text=transcript, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)['TranslatedText']
                        else:
                            print('no transript in transcripts')
                # pprint(transcribe_transcript['transcripts'])
                ## WORDS
                if 'items' in transcribe_transcript:
                    last_end_time = 0
                    for titem in transcribe_transcript['items']:
                        if titem['type'] == 'pronunciation':
                            titem['pdt'] = { 
                                'start_time' : str(datetime.timedelta(seconds=float(titem['start_time'])) + datetime_start).rstrip('0').replace(' ', 'T') + 'Z',
                                'end_time' : str(datetime.timedelta(seconds=float(titem['end_time'])) + datetime_start).rstrip('0').replace(' ', 'T') + 'Z'
                            }
                            titem['emp'] = { 
                                'start_time' : (datetime.timedelta(seconds=float(titem['start_time'])) + datetime_start).strftime("%Y-%m-%d %H:%M:%S").replace(' ', 'T') + '+00:00',
                                'end_time' : (datetime.timedelta(seconds=float(titem['end_time'])) + datetime_start).strftime("%Y-%m-%d %H:%M:%S").replace(' ', 'T') + '+00:00'
                            }
                            
                            last_end_time = titem['end_time']
                            # print('start_time_pdt: {} \t end_time: {}'.format(start_time_pdt,end_time_pdt))
                        if titem['type'] == 'punctuation':
                            titem['start_time'] = last_end_time
                            titem['end_time'] = last_end_time
                            titem['pdt'] = { 
                                'start_time' : str(datetime.timedelta(seconds=float(last_end_time)) + datetime_start).rstrip('0').replace(' ', 'T') + 'Z',
                                'end_time' : str(datetime.timedelta(seconds=float(last_end_time)) + datetime_start).rstrip('0').replace(' ', 'T') + 'Z'                                
                            }
                            titem['emp'] = { 
                                'start_time' : (datetime.timedelta(seconds=float(last_end_time)) + datetime_start).strftime("%Y-%m-%d %H:%M:%S").replace(' ', 'T') + '+00:00',
                                'end_time' : (datetime.timedelta(seconds=float(last_end_time)) + datetime_start).strftime("%Y-%m-%d %H:%M:%S").replace(' ', 'T') + '+00:00'
                            }
                # pprint(transcribe_transcript)                            
                update_dyanmo_main( {'id_filename' : item['id_filename'], 'transcribe_status' : transcribe_status, 'transcribe_transcript' : transcribe_transcript } )
            else:
                print('{} dynamo already been updated... skipping '.format(item['id_filename']))

    # return 'fake stop point'
    #### Transcribe Job Design
    print("query of table: " + str(DYNAMO_MAIN))
    table = dynamodb.Table(DYNAMO_MAIN)    
    response = table.query(
        Limit=20,
        IndexName=DYNAMO_MAIN_GSI,        
        ScanIndexForward=False,
        KeyConditionExpression=Key('id_type').eq('segment'),
    )
    full_list = {}
    for item in response['Items']:
        if item['transcribe_status'] == 'NOT_SUBMITTED':
            if item['timestamp_minute'] not in full_list:
                full_list[item['timestamp_minute']] = {'duration': float(0)}
            full_list[item['timestamp_minute']].update({str(item['timestamp_pdt']) : item['audio_file']})
            full_list[item['timestamp_minute']]['duration'] += float(item['duration'])
    pprint(full_list)
    ## set tmp directory
    tmpdir = '/tmp/' + str(uuid.uuid4()) + '/'
    ensure_dir(tmpdir)
    files_to_delete = []
    for minute, seconds in full_list.iteritems():
        if(seconds['duration'] > 49):
            files_to_concat = []
            list_of_timestamps = []
            for second, audiofile in seconds.iteritems():
                if second is not 'duration':
                    print('downloading audio for minute: {}, second: {}, filename: {}, in dir: {}'.format(minute, second, audiofile, tmpdir))
                    get_s3file(S3_BUCKET, 'audio/' + audiofile, tmpdir + audiofile)
                    list_of_timestamps.append(str(second))
                    files_to_concat.append(str(tmpdir + audiofile))
                    files_to_delete.append(str(tmpdir + audiofile))
                    update_dyanmo_main( {'id_filename' : audiofile.replace('.wav', '-001.jpg'), 'transcribe_status' : 'CONCAT', 'transcribe_transcript' : 'CONCAT' } )
            files_to_concat.sort()
            list_of_timestamps.sort()
            pprint(list_of_timestamps)
            print('first timestamp is: {}'.format(list_of_timestamps[0]))
            timestamp_start = list_of_timestamps[0]
            concat_string = SOX + ' '
            for file_to_concat in files_to_concat:
                concat_string += file_to_concat + ' '
            file_to_upload = 'stream_' + minute.replace('-','').replace(' ','').replace(':','')
            concat_string += tmpdir + file_to_upload +'.wav 2>&1'
            pprint(concat_string)
            sox_output = os.popen( concat_string ).read()
            print('sox output: {}'.format(sox_output))
            data = open(tmpdir + file_to_upload + '.wav', 'rb')
            pprint(s3.Bucket(S3_BUCKET).put_object(Key='audio/' + file_to_upload + '.wav', Body=data))
            files_to_delete.append(str(tmpdir + file_to_upload + '.wav'))
            transcribe_status = 'NOT_SUBMITTED'
            job_name = file_to_upload
            job_uri = "https://s3.amazonaws.com/" + S3_BUCKET + "/audio/" + file_to_upload + ".wav"
            transcribe.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': job_uri},
                MediaFormat='wav',
                LanguageCode='en-US',
                MediaSampleRateHertz=16000
            )
            transcribe_job = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            print('transcribe status: {}'.format(transcribe_job['TranscriptionJob']['TranscriptionJobStatus']))            
            transcribe_status = transcribe_job['TranscriptionJob']['TranscriptionJobStatus']
            dynamo_segment_object={
                'id_filename': file_to_upload + '.wav',
                'id_type': 'minute',
                'timestamp_minute': minute,
                # 'timestamp_second': datetime_datetime.strftime("%S"),
                'timestamp_start' : timestamp_start,
                'duration' : str(seconds['duration']),
                'audio_file': file_to_upload, 
                'transcribe_job' : job_name,
                'transcribe_status' : transcribe_status,
                'timestamp_created' : int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds()),
                'timestamp_ttl' : int((datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() + master_ttl) # 2 hours
            }
            put_dynamo_main(dynamo_segment_object)
                        
        else:
            print('skipping due to not enough seconds for the minute')       


            
    for file_to_delete in files_to_delete:
        delete_file(file_to_delete)

    write_json()
    return 'SUCCESS: it ran'

if __name__ == '__main__':
    ''' 
    This is to run for local testing
    '''

    XRAY = 'false' # stop xray when doing local testing
    FFPROBE = 'ffprobe' # use local mac version 
    FFMPEG = 'ffmpeg' # use local mac version 
    SOX = 'sox' # use local mac version 
    os.environ['DYNAMO_MAIN'] = "catfinder5002-main"
    os.environ['S3_BUCKET'] = 'catfinder5002-dev'
    
    print(lambda_handler(None, None))
    with open('deploy', 'w') as outfile:
        outfile.write('lambda-uploader --variables \'{"S3_BUCKET": "' + S3_BUCKET + '","DYNAMO_MAIN": "' + DYNAMO_MAIN + '" }\'')
    with open('logs', 'w') as outfile:
        outfile.write('awslogs get /aws/lambda/catfinder5002-transcribe ALL --watch')
    
