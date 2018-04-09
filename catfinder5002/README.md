# catfinder5002 "Content Aware Ads"

This is also known as "Ad Kitten" shown at CES2017, this uses the catfinder5002-parse's DynamoDB "summary" table with the catfinder5002-ads code that simulates an ADS server for AWS Elemental MediaTailor. The website is used to demostrate the end to end and is optional.

![catfinder5002 diagram](catfinder5002.png)

## How to Deploy

### Step-by-step

Instructions on how to create your own by hand.

#### Create S3 Bucket

You have two options:

1. Follow these ok instructions: [Catfinder5000 Static Webstite Hosting](../catfinder5000/LAB/1_StaticWebHosting/README.md)

2. You can ue my python script: [create_bucket.py](catfinder5002-createchannel/create_bucket.py)

#### Create MediaLive and MediaPackage Channels

You have two options:

1. Follow these awesome instructions: [AWS Live Streaming and Live-to-VOD Workshop](https://github.com/aws-samples/aws-media-services-simple-live-workflow)

1. If you already have solid IAM Roles, you can use my python script [create_channel.py](catfinder5002-createchannel/create_channel.py)

#### Create DynamoDB Tables

You have two options:

1. Follow these ok instructions: [Catfinder5000 DynamoDB](../catfinder5000/LAB/2_DynamoDB/README.md)

1. If you already have solid IAM Roles, you can use my python script [create_table.py](catfinder5002-createchannel/create_table.py)

#### Create Lambda Functions

You have two options:

1. Follow these ok instructions: [Catfinder5000 Lambda](../catfinder5000/LAB/3_Lambda/README.md)

1. Do your own method of deploying Lambdas. You can do what you want, I ain't the boss of you.

### Fully Automatic

#### CloudFormation Tempate

Standby... I'm ironing out the security policies. fun times...

## The Lambda Functions

### catfinder5002-ads

The "Ads" Lambda function simulates a ADS server by returning a valid VAST response to MediaTailor. The Labels collected from "Parse" Lambda allows this function to make a decision of which ads to play.

Intrigued? [catfinder5002-ads code](catfinder5002-ads/)

### catfinder5002-website

A varation of catfinder5002-website specific for this module. These files are placed in the S3 bucket and using the Static Webstite Hosting to display the results of the various functions used above.

Intrigued? [catfinder5002-website code](catfinder5002-website/)