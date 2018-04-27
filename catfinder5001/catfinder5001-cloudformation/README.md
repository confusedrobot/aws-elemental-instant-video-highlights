# catfinder5001 CloudFormation Templates

CloudFormation templates are available if you would like to launch catfinder5001 in your own account. If you are not familiar with AWS CloudFormation, review the online [User Guide](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html). 


## Templates

These templates are supported in regions: us-west-2 and us-east-1. Links below are for us-east-1.

- [**CoreAllResources**](https://s3.amazonaws.com/rodeolabz-us-east-1/cf5k/CoreAllResources.json) - This nested stack template will run all the other needed stacks listed below. It requires the following input parameters:

    - Stack Name - user defined
    - HLS Primary Source - URL of the primary HLS pull resource
    - HLS Secondary Source - URL of the secondary HLS pull resource (can be same as primary)
    - Enable Prekog - defaults to false; set to true if there is a particular label that you want to search for in the stream
    - Rekog Label - if Enable Prekog is true, provide the label to search for; otherwise, leave blank

**Individual Stacks**

These stacks can be run individually, if desired. However, they will have to be run **in the order they're listed** here due to dependencies. Inputs required, if any, by each template will be found in the Outputs section of the prior template that ran.

1.  [**Bucket Tables**](https://s3.amazonaws.com/rodeolabz-us-east-1/cf5k/BucketTables.json)

2.  [**IAM Resources**](https://s3.amazonaws.com/rodeolabz-us-east-1/cf5k/IAMResources.json)

3. [**AWS Elemental MediaPackage**](https://s3.amazonaws.com/rodeolabz-us-east-1/cf5k/MediaPackageResources.json)

4. [**AWS Elemental MediaLive**](https://s3.amazonaws.com/rodeolabz-us-east-1/cf5k/MediaLiveResources.json)

5. [**Parse**](https://s3.amazonaws.com/rodeolabz-us-east-1/cf5k/Parse.json)

6. [**Bucket Notify Configuration**](https://s3.amazonaws.com/rodeolabz-us-east-1/cf5k/BucketNotifyConfiguration.json)

7. [**Prekog VOD**](https://s3.amazonaws.com/rodeolabz-us-east-1/cf5k/PrekogVOD.json)

## Completion

After running the templates, you will have an S3 bucket created that will host the results of running Rekognition on your live stream. To view this page, go to **CloudFormation**. Select the **Bucket Tables Module**. In the **Outputs** tab, you will see the **S3BucketName** that has been created. In **S3**, go to this bucket, click on **Properties**, and select **Static Website Hosting**. Click on the **Endpoint** provided. 

## Cloud Resource Clean Up

Deleting a deployed stack through the CloudFormation console will remove all resources created with the template or templates previously applied **except** for the bucket created by the **Bucket Tables Module**. This one will have to be deleted manually. If you ran the **CoreAllResources** template, make sure to delete that stack, as opposed to the individual stacks (indicated by the NESTED label) that got created in the process. If you ran the individual templates one at a time, delete the stacks in reverse creation order (ie. delete the template that got created last first).


