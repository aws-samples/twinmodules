# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

import time
import boto3
import json

def watch_sqs(sqs_url:str, waittime:int=0, region:str='us-east-1', purge_queue:bool=False) -> list:
    '''
    Monitor an SQS for new messages. This is a blocking function that will
    wait until an SQS message appears.

    Parameters
    ----------
    sqs_url : str
        The url of the SQS to monitor.
    waittime : int, optional
        Time in seconds to wait for querying the SQS for new messages.
        The default is 0.
    region : str, optional
        AWS region the SQS is in.
        The default is 'us-east-1'.
    purge_queue : bool, optional
        If true, each time a message is found, the entire SQS will
        be purged of all messages before proceeding.  This is useful if you
        have many workers that could submit messages to the SQS, but you only
        want 1 downstream job to trigger.
        The default is False.

    Returns
    -------
    list
        SQS messages.

    '''

    sqs_client = boto3.client('sqs', region_name=region)

    while True:
        print("watching sqs")

        #check if messages in queue
        response = sqs_client.receive_message(
                                    QueueUrl=sqs_url,
                                    #20sec is the max allowed for sqs long polling,
                                    #using time.sleep for longer polling
                                    WaitTimeSeconds=min(waittime,20)
                                    )
        if waittime > 20:
            time.sleep(waittime-20)

        #if we found messages, delete from queue and return
        #back to parent
        lst = []
        if 'Messages' in list(response.keys()):
            print("Message found in sqs. Extracting.")
            if purge_queue:
                sqs_client.purge_queue( QueueUrl=sqs_url)
            else:
                for message in response['Messages']:
                    #leaving this code behind in case I want the SQS message contents
                    #recieptHandle = response['Messages'][0]['ReceiptHandle']
                    #body = json.loads(response['Messages'][0]['Body'])
                    #filename = body['Records'][0]['s3']['object']['key']

                    recieptHandle = message['ReceiptHandle']
                    lst.append(recieptHandle)

                    sqs_client.delete_message(
                                                QueueUrl=sqs_url,
                                                ReceiptHandle  = recieptHandle)
            break

    print("SQS: wait completed, moving on. ")
    return lst

#-------------------------------------------------------------------------------------


def create_sqs_s3(queue_name:str, account_number:str, s3_bucket_name:str) -> dict:
    '''
    Create an SQS that accepts notifications from S3 bucket triggers. Note this
    function uses the SDK and is expected to be replaced with CDK in the
    future.

    Parameters
    ----------
    queue_name : str
        Name of the SQS
    account_number : str
        Account where the SQS will be created.
    s3_bucket_name : str
        Name of the s3 bucket to accept messages from.

    Returns
    -------
    dict
        SQS queue attributes.

    '''


    #create the queue then set the access policy to enable s3 notifications
    client = boto3.client('sqs')
    response = client.create_queue(  QueueName=queue_name )

    queue_attributes = client.get_queue_attributes(QueueUrl=response['QueueUrl'],
                                            AttributeNames=['All'])

    s3_policy_update={}
    s3_policy_update['Policy'] = \
        {
        "Version": "2012-10-17",
        "Id": "auto-setup",
        "Statement": [
            {
                "Sid": "s3-events",
                "Effect": "Allow",
                "Principal": {
                    "Service": "s3.amazonaws.com"
                },
                "Action": [
                    "SQS:SendMessage"
                ],
                "Resource": queue_attributes['Attributes']['QueueArn'],
                "Condition": {
                    "ArnLike": {
                        "aws:SourceArn": "arn:aws:s3:*:*:"+ s3_bucket_name
                    },
                    "StringEquals": {
                        "aws:SourceAccount": account_number
                    }
                }
            }
        ]
    }

    s3_policy_update['Policy'] = json.dumps(s3_policy_update['Policy'])


    response = client.set_queue_attributes(
                                    QueueUrl=response['QueueUrl'],
                                    Attributes= s3_policy_update
                                )

    return queue_attributes


#-------------------------------------------------------------------------------------

def delete_sqs(queue_name:str) -> None:
    '''
    Delete an SQS. Note this
    function uses the SDK and is expected to be replaced with CDK in the
    future.

    Parameters
    ----------
    queue_name : str
        Name of the SQS to delete.

    Returns
    -------
    None

    '''

    client = boto3.client('sqs')
    response = client.list_queues(QueueNamePrefix = queue_name)

    if "QueueUrls" not in response.keys():
        print("QueueDoesNotExist.")
        return None

    for QueueUrl in response['QueueUrls']:
        try:
            client.delete_queue(
                                QueueUrl=QueueUrl
                            )
        except Exception as e:
           if "QueueDoesNotExist" in str(e):
               print("QueueDoesNotExist.")
           else:
               raise e