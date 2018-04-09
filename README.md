# Instant video highlights: build your own Live-to-VOD workflow with machine-learning image recognition

<!-- TOC -->

- [Instant video highlights: build your own Live-to-VOD workflow with machine-learning image recognition](#instant-video-highlights-build-your-own-live-to-vod-workflow-with-machine-learning-image-recognition)
    - [catfinder5001 "the original"](#catfinder5001-the-original)
        - [catfinder5001-parse](#catfinder5001-parse)
        - [catfinder5001-prekog](#catfinder5001-prekog)
        - [catfinder5001-vod](#catfinder5001-vod)
        - [catfinder5001-website](#catfinder5001-website)
    - [catfinder5002 "Content Aware Ads"](#catfinder5002-content-aware-ads)
        - [catfinder5002-ads](#catfinder5002-ads)
        - [catfinder5002-website](#catfinder5002-website)
    - [catfinder5003 "Auomated Transcribe and Translate"](#catfinder5003-auomated-transcribe-and-translate)
        - [catfinder5003-parse](#catfinder5003-parse)
        - [catfinder5003-transcribe](#catfinder5003-transcribe)
        - [catfinder5003-website](#catfinder5003-website)
    - [catfinder5004 "Automated Sports Clipping"](#catfinder5004-automated-sports-clipping)
        - [catfinder5004-parse](#catfinder5004-parse)
        - [catfinder5004-website](#catfinder5004-website)

<!-- /TOC -->
Demonstration of a frame accurate live-to-VOD solution with automatic machine-learning image recognition Introduction to the AWS services used to create the demonstration Explanation of how the services were combined to create a solution

## catfinder5001 "the original"

This is a refactor of the original "catfinder 5000" shown at re:Invent 2017 that used AWS Elemental Delta to now use the new AWS Media Services. The OG CF5k required a polling technique on the HLS manifest, which now with CF5k1 we can use the seamless integration of AWS Elemental MediaLive with S3 and AWS Elemental MediaPackage in place of AWS Elemental Delta.

![catfinder5001 diagram](catfinder5001.png)

Interested? [catfinder5001 Deployment Instructions](catfinder5001/)

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

## catfinder5002 "Content Aware Ads"

This is also known as "Ad Kitten" shown at CES2017, this uses the catfinder5001-parse's DynamoDB "summary" table with the catfinder5002-ads code that simulates an ADS server for AWS Elemental MediaTailor. The website is used to demostrate the end to end and is optional. 

![catfinder5002 diagram](catfinder5002.png)

Interested? [catfinder5002 Deployment Instructions](catfinder5002/)

### catfinder5002-ads

Note: This requires catfinder5001-parse to work

The "Ads" Lambda function simulates a ADS server by returning a valid VAST response to MediaTailor. The Labels collected from "Parse" Lambda allows this function to make a decision of which ads to play.

Intrigued? [catfinder5002-ads code](catfinder5002-ads/)

### catfinder5002-website

A varation of catfinder5001-website specific for this module. These files are placed in the S3 bucket and using the Static Webstite Hosting to display the results of the various functions used above.

Intrigued? [catfinder5002-website code](catfinder5002-website/)

## catfinder5003 "Auomated Transcribe and Translate"

This is an evolution of the OG catfinder5001 that includes the ability to extend analysis from visual ( Amazon Rekognition ) to audible ( Amazon Translate ). The transcription of the livestream is then thrown throw Amazon Translate and Amazon Comprehend and displayed in a nifty webpage interface. One could easily append an automation with these results, and that part is up to you!

![catfinder5003 diagram](catfinder5003.png)

Interested? [catfinder5003 Deployment Instructions](catfinder5003/)

### catfinder5003-parse

This is a slight variation of catfinder5001-parse that also generates WAV files to be used for the catfinder5003-transcribe code.

Intrigued? [catfinder5003-parse code](catfinder5003-parse/)

### catfinder5003-transcribe

The "Transcribe" Lambda function uses the WAV files created by the "Parse" Lambda function to concat them in to a 1 minute audio archive. These 1 minute WAV file is then passed to Amazon Transcribe and the results are placed in the DynamoDB database. These results are also passed to Amazon Translate and Amazon Comprehend.

Intrigued? [catfinder5003-transcribe code](catfinder5003-transcribe/)

### catfinder5003-website

A varation of catfinder5001-website specific for this module. These files are placed in the S3 bucket and using the Static Webstite Hosting to display the results of the various functions used above.

Intrigued? [catfinder5003-website code](catfinder5003-website/)

## catfinder5004 "Automated Sports Clipping"

This version uses the basis of catfinder5001-parse but is designed to monitor a scoreboard of a Hockey Livestream and make decisions based upon a "Goal" ( increase of score ) and a "Shot" ( increase of the shot clock ). This is a work in progress and was hardcoded for the NAB2018 demo. It was very scrappy and is not complete. I would not suggest using this as-is, but I am including the code as I make it more robust.

![catfinder5004 diagram](catfinder5004.png)

Interested? [catfinder5001 Deployment Instructions](catfinder5004/)

### catfinder5004-parse

This is a heavy variation of catfinder5001-parse that has been hardcoded to specific content that was provided for NAB2018 at the AWS Elemental Booth.

Intrigued? [catfinder5004-parse code](catfinder5004-parse/)

### catfinder5004-website

this is a heavy variation of catfinder5003-website specific for the NAB2018 demo.

Intrigued? [catfinder5004-website code](catfinder5004-website/)
