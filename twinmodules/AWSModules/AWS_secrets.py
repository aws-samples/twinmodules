# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name:str, region_name:str) -> dict:
    '''
    Assuming the proper IAM permissions are set, a python
    script can utilize this function to grab the AWS managed
    secrets to access other services such as databases.

    This enables developers to create pipelines that utilize
    proper security protocols without hard coding security
    information.

    Parameters
    ----------
    secret_name : str
        Name of the AWS Secret to grab.
    region_name : str
        Region where this secret resides.


    Returns
    -------
    dict
        A dictionary of secret information, including
        the username and password.

    '''
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response['SecretString']
    secret = eval(secret)

    # Your code goes here.
    return secret