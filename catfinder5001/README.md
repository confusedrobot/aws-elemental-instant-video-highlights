# catfinder5001 "the original"

This is a refactor of the original "catfinder 5000" shown at re:Invent 2017 that used AWS Elemental Delta to now use the new AWS Media Services. The OG CF5k required a polling technique on the HLS manifest, which now with CF5k1 we can use the seamless integration of AWS Elemental MediaLive with S3 and AWS Elemental MediaPackage in place of AWS Elemental Delta.

![catfinder5001 diagram](catfinder5001.png)

## How to Deploy

### Step-by-step

Instructions on how to create your own by hand.

#### Create S3 Bucket

You have two options:

1. Follow these ok instructions: [Catfinder5000 Static Webstite Hosting](../catfinder5000/LAB/1_StaticWebHosting/README.md)

2. You can ue my python script: [create_bucket.py](catfinder5001-createchannel/create_bucket.py)

#### Create MediaLive and MediaPackage Channels

You have two options:

1. Follow these awesome instructions: [AWS Live Streaming and Live-to-VOD Workshop](https://github.com/aws-samples/aws-media-services-simple-live-workflow)

1. If you already have solid IAM Roles, you can use my python script [create_channel.py](catfinder5001-createchannel/create_channel.py)

#### Create DynamoDB Tables

You have two options:

1. Follow these ok instructions: [Catfinder5000 DynamoDB](../catfinder5000/LAB/2_DynamoDB/README.md)

1. If you already have solid IAM Roles, you can use my python script [create_table.py](catfinder5001-createchannel/create_table.py)

#### Create Lambda Functions

You have two options:

1. Follow these ok instructions: [Catfinder5000 Lambda](../catfinder5000/LAB/3_Lambda/README.md)

1. Do your own method of deploying Lambdas. You can do what you want, I ain't the boss of you.

### Fully Automatic

#### CloudFormation Tempate

Standby... I'm ironing out the security policies. fun times...

## The Lambda Functions

### catfinder5001-parse

CatFinder5000 is Lambda function that parses a MediaLive's HLS output from a S3 PUT Cloudwatch Event. The "Parse" Lambda function looks for signficant changes in the video by utilizing the FFPROBE's lavfi "scene" filter. Then using FFMPEG, that scene is extracting into a jpeg that is used to invoke Amazon Rekognition. These results are then placed into a DynamoDB database so that other "modules" can utilize this data.

Intrigued? [catfinder5001-parse code](catfinder5001-parse/)

### catfinder5001-prekog

CatFinder5001 was the first catfinder "module" created. The "Prekog" Lambda function is invoked when a desired Rekognition Label has been detected. The lambda function then utlizes the DynamoDB table to discover when the Label was first detected and when the Label was no longer in the scene using scene accurate timestamps. The catfinder5001-vod Lambda function is invoked with these timestamps.

Intrigued? [catfinder5001-prekog code](catfinder5001-prekog/)

### catfinder5001-vod

The "VOD" Lambda function uses the timestamps passed from "Prekog" to download HLS segment files from MediaPackage's Time-shifted Viewing feature Start/End URL Parameters to the S3 bucket. To achieve frame-accuracy, the "VOD" Lambda function then invokes a MediaConvert job's Input Clipping feature which results in an MP4 file in the same S3 bucket. The DynamoDB database is updated with this location so the Website UI can display a player of this video.

Intrigued? [catfinder5001-vod code](catfinder5001-vod/)

### catfinder5001-website

These files are placed in the S3 bucket and using the Static Webstite Hosting to display the results of the various functions used above.

Intrigued? [catfinder5001-website code](catfinder5001-website/)