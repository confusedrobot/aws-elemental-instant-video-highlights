# catfinder5002 "Content Aware Ads"

This is also known as "Ad Kitten" shown at CES2017, this uses the catfinder5001-parse's DynamoDB "summary" table with the catfinder5002-ads code that simulates an ADS server for AWS Elemental MediaTailor. The website is used to demostrate the end to end and is optional. 

![catfinder5002 diagram](catfinder5002.png)

## catfinder5002-ads

The "Ads" Lambda function simulates a ADS server by returning a valid VAST response to MediaTailor. The Labels collected from "Parse" Lambda allows this function to make a decision of which ads to play.

Intrigued? [catfinder5002-ads code](catfinder5002-ads/)

## catfinder5002-website

A varation of catfinder5001-website specific for this module. These files are placed in the S3 bucket and using the Static Webstite Hosting to display the results of the various functions used above.

Intrigued? [catfinder5002-website code](catfinder5002-website/)
