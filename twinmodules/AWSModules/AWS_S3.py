# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

import boto3
import awswrangler as wr
import pandas

def s3_object_exist(object_name:str, s3_bucket_name:str) -> bool:
    '''
    Determine if an object exists in a specific s3 bucket.

    Parameters
    ----------
    object_name : str
        Can include s3 key
    s3_bucket_name : str

    Returns
    -------
    bool
        True if it exists.

    '''

    from botocore.exceptions import ClientError

    client = boto3.client('s3')

    try:
        client.get_object(Bucket=s3_bucket_name,
                          Key=object_name)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return False

#----------------------------------------------------------------------------------------------
def s3_all_contents(folder_name:str, s3_bucket_name:str) -> list[str]:
    '''
    Return a list of all objects in an s3 bucket.

    Parameters
    ----------
    folder_name : str
        Folder or s3 key name, can be '' if looking for objects in
        root s3 bucket directory.
    s3_bucket_name : str

    Returns
    -------
    list[str]
        A list of all objects in a specific
        s3_bucket_name/folder_name
    '''

    client = boto3.client('s3')

    paginator = client.get_paginator('list_objects')
    lst = []
    for response in paginator.paginate(Bucket=s3_bucket_name,
                                       Prefix=folder_name):
        for rep in response['Contents']:
            #ensure we dont send back folder names
            if rep['Size'] > 1:
                lst.append(   rep['Key'])

    return lst

#----------------------------------------------------------------------------------------------
def get_data_s3(local_data_path: str,
                file_to_get: str,
                bucket_name: str) -> None:
    '''
    Download an s3 object from the 'bucket_name'.

    First checks if object exists, if not a warning is thrown
    and the function returns none.

    Parameters
    ----------
    local_data_path : str
        Location on the local file system to copy the object into.
    file_to_get : str
        The s3 object name to download, can include the s3 key if
        multiple folders in the bucket.
    bucket_name : str

    Returns
    -------
    None

    '''

    conn = boto3.client('s3')
    if s3_object_exist(file_to_get, bucket_name):
        conn.download_file(bucket_name, file_to_get, local_data_path)
    else:
        print(f"WARNING: file {file_to_get} does not exist in {bucket_name}.")

#----------------------------------------------------------------------------------------------
def send_data_s3(local_data_path:str,
                 remote_filename: str,
                 bucket_name: str) -> None:
    '''
    Simple pass through to boto3. Included for completeness.

    Parameters
    ----------
    local_data_path : str
        File include path to be uploaded to the s3 bucket.
    remote_filename : str
        The name with key to upload to the s3 bucket.
    bucket_name : str

    Returns
    -------
    None

    '''

    conn = boto3.client('s3')
    conn.upload_file(local_data_path, bucket_name, remote_filename)

#----------------------------------------------------------------------------------------------

def stream_send_s3_csv(df:pandas.DataFrame,
                       remote_filename: str,
                       bucket_name: str) -> None:
    '''
    Directly upload a pandas dataframe to a csv file in an s3 bucket.

    Simple pass through to awswrangler, very likely deprecate this function
    since it currently adds little value.

    See awswrangler for many more options:
    https://aws-sdk-pandas.readthedocs.io/en/stable/stubs/awswrangler.s3.to_csv.html#awswrangler.s3.to_csv

    Parameters
    ----------
    df : pandas.DataFrame
    remote_filename : str
        Can include s3 key
    bucket_name : str

    Returns
    -------
    None

    '''

    wr.s3.to_csv( df=df,  path=f's3://{bucket_name}/{remote_filename}' , index=False)

#----------------------------------------------------------------------------------------------

def stream_get_s3_csv( remote_filename: str,
                       bucket_name: str) -> pandas.DataFrame:
    '''

    Directly download a csv file into a pandas dataframe.

    Simple pass through to awswrangler, very likely deprecate this function
    since it currently adds little value.

    This function does check if the s3 object exists first and will return a blank
    dataframe if the file does not exist.

    See awswrangler for many more options:
    https://aws-sdk-pandas.readthedocs.io/en/stable/stubs/awswrangler.s3.read_csv.html#awswrangler.s3.read_csv

    Parameters
    ----------
    remote_filename : str
        Remote file including s3 key
    bucket_name : str

    Returns
    -------
    pandas.DataFrame

    '''

    if s3_object_exist(remote_filename, bucket_name):
        df = wr.s3.read_csv(path=f's3://{bucket_name}/{remote_filename}')
        return df
    else:
        print(f"File {remote_filename} not found.")
        return pandas.DataFrame()


#----------------------------------------------------------------------------------------------
def delete_data_s3(remote_filename: str,
                   bucket_name: str) -> None:
    '''
    Delete an object from s3 bucket.

    Parameters
    ----------
    remote_filename : str
        Object to delete, can include s3 key.
    bucket_name : str

    Returns
    -------
    None

    '''

    conn = boto3.client('s3')
    conn.delete_object( Bucket = bucket_name,
                        Key = remote_filename  )

#----------------------------------------------------------------------------------------------


def create_s3_buckets(s3_bucket_name:str,
                      region:str) -> None:
    '''
    Create an s3 bucket using the SDK.  All public access
    to this bucket will be shutoff. Note this function is
    expected to be replaced with CDK in the future.

    Parameters
    ----------
    s3_bucket_name : str
    region : str
        AWS region where the bucket will be created

    Returns
    -------
    None

    '''

    client = boto3.client('s3')
    try:
        client.create_bucket(
                             Bucket=s3_bucket_name
                             )
        client.put_public_access_block(
                            Bucket=s3_bucket_name,
                            PublicAccessBlockConfiguration={
                                "BlockPublicPolicy":True,
                                "IgnorePublicAcls":True,
                                "BlockPublicAcls":True,
                                "RestrictPublicBuckets":True}
                            )

    except Exception as e:
       if "BucketAlreadyExists" in str(e):
           print("Bucket already exists.")
       else:
           raise e

#-------------------------------------------------------------------------------------

#TODO: at some point probably want the notification type to be user modifiable
def setup_s3_notifications(s3_bucket_name:str, queue_attributes:str, notification_name:str, prefix:str) -> None:
    '''
    Setup event notifications for an s3 bucket. This uses the AWS SDK and
    is expected to be replaced with CDK in the future.

    Parameters
    ----------
    s3_bucket_name : str
    queue_attributes : str
        The notifications will be sent to the SQS at this ARN.
    notification_name : str
    prefix : str
        Only look at changes for objects with this prefix (i.e. objects in this s3 folder)

    Returns
    -------
    None


    '''

    notification_type = ['s3:ObjectCreated:*',
                         's3:ObjectRemoved:*']

    client = boto3.client('s3')

    response = client.get_bucket_notification_configuration(   Bucket=s3_bucket_name)

    Qconfig = [{
        'Id': notification_name,
        'QueueArn': queue_attributes['Attributes']['QueueArn'],
        'Events': notification_type,
        'Filter': {
            'Key': {
                'FilterRules': [
                    {
                        'Name': 'prefix',
                        'Value': prefix
                    },
                ]
            }
        }
    }]
    if response['QueueConfigurations']:
        Qconfig.extend(response['QueueConfigurations'])


    response = client.put_bucket_notification_configuration(
        Bucket=s3_bucket_name ,
        NotificationConfiguration={
            'QueueConfigurations': Qconfig
        }
    )



#-------------------------------------------------------------------------------------

def delete_s3_bucket(s3_bucket_name:str, account_number:str) -> None:
    '''
    Delete the s3 bucket. Note this uses the AWS SDK and is
    expected to be replaced with CDK in the future. Users
    are assumed to have proper IAM access or this function
    will fail for security reasons.

    Parameters
    ----------
    s3_bucket_name : str
    account_number : str
        The account where the s3 bucket resides.

    Returns
    -------
    None

    '''
    client = boto3.client('s3')
    try:
        response = client.delete_bucket(
                                        Bucket=s3_bucket_name,
                                        ExpectedBucketOwner=account_number
                                    )
    except Exception as e:
       if "NoSuchBucket" in str(e):
           print("NoSuchBucket.")
       else:
           raise e

