from __future__ import print_function # Python 2/3 compatibility
import boto3
from pprint import pprint
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
autoscaling = boto3.client('application-autoscaling')

def create_table_main(table_name):
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {
                "KeyType": "HASH", 
                "AttributeName": "id_filename"
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "id_filename", 
                "AttributeType": "S"
            }, 
            {
                "AttributeName": "id_type", 
                "AttributeType": "S"
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        },
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'id_type-id_filename-index',
                'KeySchema': [
                    {
                        "KeyType": "HASH", 
                        "AttributeName": "id_type"
                    }, 
                    {
                        "KeyType": "RANGE", 
                        "AttributeName": "id_filename"
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL',
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 10,
                    'WriteCapacityUnits': 10
                }
            },
        ]
    )

    print("Table status:", table.table_status)

def create_table_summary(table_name):
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {
                "KeyType": "HASH", 
                "AttributeName": "rekog_label"
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "rekog_label", 
                "AttributeType": "S"
            }, 
            {
                "AttributeName": "rekog_type", 
                "AttributeType": "S"
            }, 
            {
                "AttributeName": "timestamp_updated", 
                "AttributeType": "N"
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 20,
            'WriteCapacityUnits': 20
        },
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'rekog_type-timestamp_updated-index',
                'KeySchema': [
                    {
                        "KeyType": "HASH", 
                        "AttributeName": "rekog_type"
                    }, 
                    {
                        "KeyType": "RANGE", 
                        "AttributeName": "timestamp_updated"
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL',
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 20,
                    'WriteCapacityUnits': 20
                }
            },
        ]
    )

    print("Table status:", table.table_status)

def create_table_list(table_name):
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {
                "KeyType": "HASH", 
                "AttributeName": "label"
            }, 
            {
                "KeyType": "RANGE", 
                "AttributeName": "label_sort"
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "label", 
                "AttributeType": "S"
            }, 
            {
                "AttributeName": "label_sort", 
                "AttributeType": "S"
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
 
    )

    print("Table status:", table.table_status)

def add_autoscaler(table_name):
    response = autoscaling.register_scalable_target(
        ServiceNamespace='dynamodb',
        ResourceId='table/' + table_name,
        ScalableDimension='dynamodb:table:WriteCapacityUnits',
        MinCapacity=5,
        MaxCapacity=100,
        RoleARN='arn:aws:iam::463540299421:role/service-role/DynamoDBAutoscaleRole'
    )
    pprint(response)
    response = autoscaling.register_scalable_target(
        ServiceNamespace='dynamodb',
        ResourceId='table/' + table_name,
        ScalableDimension='dynamodb:table:ReadCapacityUnits',
        MinCapacity=5,
        MaxCapacity=100,
        RoleARN='arn:aws:iam::463540299421:role/service-role/DynamoDBAutoscaleRole'
    )
    pprint(response)
def check_autscaler(table_name):
    response = autoscaling.describe_scalable_targets(
        ServiceNamespace='dynamodb',
        ResourceIds=[
            'table/' + table_name,
        ],
        ScalableDimension='dynamodb:table:ReadCapacityUnits',
        MaxResults=3,
        # NextToken='string'
    )    
    pprint(response)
    response = autoscaling.describe_scalable_targets(
        ServiceNamespace='dynamodb',
        ResourceIds=[
            'table/' + table_name,
        ],
        ScalableDimension='dynamodb:table:WriteCapacityUnits',
        MaxResults=3,
        # NextToken='string'
    )    
    pprint(response)
       

if __name__ == '__main__':
    # create main table
    create_table_main('nab2018-catfinder5003-main')
    # add_autoscaler('nab2018-catfinder5003-main')
    # check_autscaler('nab2018-catfinder5003-main')
    # create summary table
    create_table_summary('nab2018-catfinder5003-summary')
    # add_autoscaler('nab2018-catfinder5003-summary')
    # check_autscaler('nab2018-catfinder5003-summary')    
    # create list table
    create_table_list('nab2018-catfinder5003-list')
    # add_autoscaler('nab2018-catfinder5003-list')
    # check_autscaler('nab2018-catfinder5003-list')        