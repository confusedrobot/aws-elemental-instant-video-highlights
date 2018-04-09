# catfinder5003 "Auomated Transcribe and Translate"

This is an evolution of the OG catfinder5001 that includes the ability to extend analysis from visual ( Amazon Rekognition ) to audible ( Amazon Translate ). The transcription of the livestream is then thrown throw Amazon Translate and Amazon Comprehend and displayed in a nifty webpage interface. One could easily append an automation with these results, and that part is up to you!

![catfinder5003 diagram](catfinder5003.png)

## catfinder5003-parse

This is a slight variation of catfinder5001-parse that also generates WAV files to be used for the catfinder5003-transcribe code.

Intrigued? [catfinder5003-parse code](catfinder5003-parse/)

## catfinder5003-transcribe

The "Transcribe" Lambda function uses the WAV files created by the "Parse" Lambda function to concat them in to a 1 minute audio archive. These 1 minute WAV file is then passed to Amazon Transcribe and the results are placed in the DynamoDB database. These results are also passed to Amazon Translate and Amazon Comprehend.

Intrigued? [catfinder5003-transcribe code](catfinder5003-transcribe/)

## catfinder5003-website

A varation of catfinder5001-website specific for this module. These files are placed in the S3 bucket and using the Static Webstite Hosting to display the results of the various functions used above.

Intrigued? [catfinder5003-website code](catfinder5003-website/)