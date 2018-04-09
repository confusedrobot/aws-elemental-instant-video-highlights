# Instant video highlights: build your own Live-to-VOD workflow with machine-learning image recognition

Demonstration of a frame accurate live-to-VOD solution with automatic machine-learning image recognition Introduction to the AWS services used to create the demonstration Explanation of how the services were combined to create a solution

## catfinder5000-parse

CatFinder5000 is Lambda function that parses a MediaLive's HLS output from a S3 PUT Cloudwatch Event. The "Parse" Lambda function looks for signficant changes in the video by utilizing the FFPROBE's lavfi "scene" filter. Then using FFMPEG, that scene is extracting into a jpeg that is used to invoke Amazon Rekognition. These results are then placed into a DynamoDB database so that other "modules" can utilize this data. 

## catfinder5001-prekog

CatFinder5001 was the first catfinder "module" created. The "Prekog" Lambda function is invoked when a desired Rekognition Label has been detected. The lambda function then utlizes the DynamoDB table to discover when the Label was first detected and when the Label was no longer in the scene using scene accurate timestamps. The catfinder5001-vod Lambda function is invoked with these timestamps. 

## catfinder5001-vod

The "VOD" Lambda function uses the timestamps passed from "Prekog" to download HLS segment files from MediaPackage's Time-shifted Viewing feature Start/End URL Parameters to the S3 bucket. To achieve frame-accuracy, the "VOD" Lambda function then invokes a MediaConvert job's Input Clipping feature which results in an MP4 file in the same S3 bucket. The DynamoDB database is updated with this location so the Website UI can display a player of this video. 

## catfinder5002-ads

The "Ads" Lambda function simulates a ADS server by returning a valid VAST response to MediaTailor. The Labels collected from "Parse" Lambda allows this function to make a decision of which ads to play.

## catfinder5003-transcribe

The "Transcribe" Lambda function uses the WAV files created by the "Parse" Lambda function to concat them in to a 1 minute audio archive. These 1 minute WAV file is then passed to Amazon Transcribe and the results are placed in the DynamoDB database. These results are also passed to Amazon Translate and Amazon Comprehend. 

## catfinder5000-website

These files are placed in the S3 bucket and using the Static Webstite Hosting to display the results of the various functions used above.

## AWS Services used under the hood

![](catfinder5001.png)

