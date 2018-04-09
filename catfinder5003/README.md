# catfinder5003 "Auomated Transcribe and Translate"

This is an evolution of the OG catfinder5001 that includes the ability to extend analysis from visual ( Amazon Rekognition ) to audible ( Amazon Translate ). The transcription of the livestream is then thrown throw Amazon Translate and Amazon Comprehend and displayed in a nifty webpage interface. One could easily append an automation with these results, and that part is up to you!

![catfinder5003 diagram](catfinder5003.png)

## How to Deploy

### Step-by-step

Instructions on how to create your own by hand.

#### Create S3 Bucket

You have two options:

1. Follow these ok instructions: [Catfinder5000 Static Webstite Hosting](catfinder5000/LAB/1_StaticWebHosting/README.md)

2. You can ue my python script: [create_bucket.py](catfinder5003-createchannel/create_bucket.py)

#### Create MediaLive and MediaPackage Channels

You have two options:

1. Follow these awesome instructions: [AWS Live Streaming and Live-to-VOD Workshop](https://github.com/aws-samples/aws-media-services-simple-live-workflow)

1. If you already have solid IAM Roles, you can use my python script [create_channel.py](catfinder5003-createchannel/create_channel.py)

#### Create DynamoDB Tables

You have two options:

1. Follow these ok instructions: [Catfinder5000 DynamoDB](../catfinder5000/LAB/2_DynamoDB/README.md)

1. If you already have solid IAM Roles, you can use my python script [create_table.py](catfinder5003-createchannel/create_table.py)

#### Create Lambda Functions

You have two options:

1. Follow these ok instructions: [Catfinder5000 Lambda](../catfinder5000/LAB/3_lambda/README.md)

1. Do your own method of deploying Lambdas. You can do what you want, I ain't the boss of you.

### Fully Automatic

#### CloudFormation Tempate

Standby... I'm ironing out the security policies. fun times...

## The Lambda Functions

### catfinder5003-parse

This is a slight variation of catfinder5001-parse that also generates WAV files to be used for the catfinder5003-transcribe code.

Intrigued? [catfinder5003-parse code](catfinder5003-parse/)

### catfinder5003-transcribe

The "Transcribe" Lambda function uses the WAV files created by the "Parse" Lambda function to concat them in to a 1 minute audio archive. These 1 minute WAV file is then passed to Amazon Transcribe and the results are placed in the DynamoDB database. These results are also passed to Amazon Translate and Amazon Comprehend.

Intrigued? [catfinder5003-transcribe code](catfinder5003-transcribe/)

### catfinder5003-website

A varation of catfinder5001-website specific for this module. These files are placed in the S3 bucket and using the Static Webstite Hosting to display the results of the various functions used above.

Intrigued? [catfinder5003-website code](catfinder5003-website/)