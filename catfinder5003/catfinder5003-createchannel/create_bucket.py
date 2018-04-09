from __future__ import print_function # Python 2/3 compatibility
import boto3
from pprint import pprint
import json
import re

# Create an S3 client

def create_bucket(bucket_name):
    s3_client = boto3.client('s3')
    s3 = boto3.resource('s3')
    bucket = s3.create_bucket(Bucket=bucket_name)    
    bucket_policy = s3.BucketPolicy(bucket_name)

    s3_permissions_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AddPerm",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource":["arn:aws:s3:::%s/*" % bucket_name]
            }
        ]
    })
    
    bucket_policy.put(Policy=s3_permissions_policy)

    # Add cors configuration
    # Default CORS is actaully okay

    # Create the configuration for the website
    website_configuration = {
        'ErrorDocument': {'Key': 'error.html'},
        'IndexDocument': {'Suffix': 'index.html'},
    }

    # Set the new policy on the selected bucket
    s3_client.put_bucket_website(
        Bucket=bucket_name,
        WebsiteConfiguration=website_configuration
    )

    # Set cloud watch events
    ## TODO
    # response = client.get_bucket_notification(
    #     Bucket='string'
    # )

if __name__ == '__main__':
    create_bucket('nab2018-catfinder5003')
