# catfinder5001-parse

## Overview

### Overview of “Parsing” lambda

S3 event triggers a parsing of the video URL every time a segment is writting to S3.
Get a time reference from Program-Date-Time information
Create a static JPG image from the scene in the video segment, stored in Amazon S3
Invoke Amazon Rekognition to tell what is on the scene, with what confidence level
Store the Time reference information, frame numbers and Delta URL in the Amazon DynamoDB

## Code Steps

1. describe MediaLive channel

1. parse out s3 and HLS locations

1. download m3u8s save to /tmp

1. parse m3u8s to get stream and time info

1. download .ts video file

1. ffprobe for PTS values and scene change analysis

1. ffmpeg for thumbnails of every frame to /tmp

1. identify each thumbnail for a scenechange indication

1. upload thumnail to S3 bucket

1. Rekognition anaylsis of thumbnail

1. if "person" label, use Celebrity Rekognition

1. put all info into DynamoDB

1. if "Cat" label detected invoke "prekog" Lambda Function

1. delete jpg and ts files

1. write json file from DynamoDB info

## Environment Variables

### Mandatory

*CHANNEL_NAME*

*DYNAMO_MAIN*

*DYNAMO_SUMMARY*

### Optional

you can override the defaults listed below with the Enviornment Variable.

*DYNAMO_MAIN* = "catfinder5000-main"

*DYNAMO_SUMMARY_GSI* = 'rekog_type-timestamp_updated-index'

*LAMBDA_PREKOG* = "catfinder5000-prekog"

*REKOG_LABEL* = "Cat"