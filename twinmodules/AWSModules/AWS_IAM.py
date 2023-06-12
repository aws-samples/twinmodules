# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################
"""
Additional information for assigning roles:

    https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html#attach-iam-role

"""

import boto3
import json


#TODO: lets revisit at some point to check if I went overkill here
# note because of the limitation of 10 policies per role, I am now
# combining many policies into one new policy
policies_to_attach = [
    #"arn:aws:iam::aws:policy/AmazonEC2FullAccess",
    #"arn:aws:iam::aws:policy/AmazonSQSFullAccess",
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    #"arn:aws:iam::aws:policy/AmazonS3FullAccess",
    #"arn:aws:iam::aws:policy/AWSBatchFullAccess",
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role",
    "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole"
]




#-------------------------------------------------------------

def is_role_available(iam:boto3.client, rolename:str) -> str and str:
    roleARN = ""
    full_name=""
    found = False
    paginator = iam.get_paginator('list_roles')
    for response in paginator.paginate(PathPrefix="/"):
        for roles in response['Roles']:
            if rolename in roles['RoleName']:
                found = True
                roleARN = roles['Arn']
                full_name = roles['RoleName']
                break
        if found:
            break
    return roleARN, full_name

#-------------------------------------------------------------

def is_policy_available(iam:boto3.client, policyname:str) -> str and str:
    policyARN = ""
    full_name=""
    found = False
    paginator = iam.get_paginator('list_policies')
    for response in paginator.paginate(PathPrefix="/"):
        for policies in response['Policies']:
            if policyname in policies['PolicyName']:
                found = True
                policyARN = policies['Arn']
                full_name = policies['PolicyName']
                break
        if found:
            break
    return policyARN, full_name

#-------------------------------------------------------------

def create_role(iam:boto3.client, roleName:str) -> None:

    trust_policy_document =    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "ec2.amazonaws.com",
                        "eks.amazonaws.com",
                        "ecs-tasks.amazonaws.com"
                    ]
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    response = iam.create_role(
        RoleName = roleName,
        AssumeRolePolicyDocument = json.dumps(trust_policy_document)  )

    if not response:
        raise ValueError("ERROR: unable to create IAM role. ")

    #attach all of the policies to this role based on the policies_to_attach list
    attach_policies(iam, roleName)


#-------------------------------------------------------------
def attach_policies(iam:boto3.client, roleName:str, single_policy:str = None) -> None:

    if single_policy is not None:
        response = iam.attach_role_policy(
            RoleName= roleName,
            PolicyArn= single_policy )
    else:
        #attach all of the policies to this role based on the policies_to_attach list
        for policy_arn in policies_to_attach:
            response = iam.attach_role_policy(
                RoleName= roleName,
                PolicyArn= policy_arn )

            if not response:
                raise ValueError(f"ERROR: unable to attach policy {policy_arn}. ")


#-------------------------------------------------------------

def create_twinflow_policy(iam:boto3.client, roleARN:str) -> str:

    twinflow_policy_name = 'TwinFlow-general-policy'

    #check if policy already made
    policyARN = is_policy_available(iam, twinflow_policy_name)
    if policyARN[0]:
        return policyARN[0]


    account_number = roleARN.split(':')[4]
    newPolicy = \
        {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "VisualEditor0",
                "Effect": "Allow",
                "Action": [
                    "sqs:DeleteMessage",
                    "sqs:GetQueueUrl",
                    "sqs:ChangeMessageVisibility",
                    "sqs:ReceiveMessage",
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:ListQueueTags",
                    "iam:PassRole",
                    "sqs:ListDeadLetterSourceQueues",
                    "sqs:PurgeQueue",
                    "sqs:DeleteQueue",
                    "sqs:CreateQueue",
                    "sqs:SetQueueAttributes"
                ],
                "Resource": [
                    "arn:aws:sqs:*:{}:*".format(account_number),
                    roleARN
                ]
            },
            {
                "Sid": "VisualEditor1",
                "Effect": "Allow",
                "Action": [
                    "s3:ListAccessPointsForObjectLambda",
                    "s3:DeleteAccessPoint",
                    "s3:DeleteAccessPointForObjectLambda",
                    "s3:PutLifecycleConfiguration",
                    "s3:DeleteObject",
                    "s3:CreateMultiRegionAccessPoint",
                    "s3:GetBucketWebsite",
                    "s3:GetMultiRegionAccessPoint",
                    "s3:PutReplicationConfiguration",
                    "s3:GetObjectAttributes",
                    "s3:InitiateReplication",
                    "s3:GetObjectLegalHold",
                    "s3:GetBucketNotification",
                    "s3:GetReplicationConfiguration",
                    "s3:DescribeMultiRegionAccessPointOperation",
                    "s3:PutObject",
                    "s3:PutBucketNotification",
                    "s3:CreateJob",
                    "s3:PutBucketObjectLockConfiguration",
                    "s3:GetStorageLensDashboard",
                    "s3:GetLifecycleConfiguration",
                    "s3:GetBucketTagging",
                    "s3:GetInventoryConfiguration",
                    "s3:GetAccessPointPolicyForObjectLambda",
                    "s3:ListBucket",
                    "s3:AbortMultipartUpload",
                    "s3:UpdateJobPriority",
                    "s3:DeleteBucket",
                    "s3:PutBucketVersioning",
                    "s3:GetMultiRegionAccessPointPolicyStatus",
                    "s3:ListBucketMultipartUploads",
                    "s3:PutIntelligentTieringConfiguration",
                    "s3:PutMetricsConfiguration",
                    "s3:GetBucketVersioning",
                    "s3:GetAccessPointConfigurationForObjectLambda",
                    "s3:PutInventoryConfiguration",
                    "s3:GetMultiRegionAccessPointRoutes",
                    "s3:GetStorageLensConfiguration",
                    "s3:DeleteStorageLensConfiguration",
                    "s3:GetAccountPublicAccessBlock",
                    "s3:PutBucketWebsite",
                    "s3:ListAllMyBuckets",
                    "s3:PutBucketRequestPayment",
                    "s3:PutObjectRetention",
                    "s3:CreateAccessPointForObjectLambda",
                    "s3:GetBucketCORS",
                    "s3:GetObjectVersion",
                    "s3:PutAnalyticsConfiguration",
                    "s3:PutAccessPointConfigurationForObjectLambda",
                    "s3:GetObjectVersionTagging",
                    "s3:PutStorageLensConfiguration",
                    "s3:CreateBucket",
                    "s3:GetStorageLensConfigurationTagging",
                    "s3:ReplicateObject",
                    "s3:GetObjectAcl",
                    "s3:GetBucketObjectLockConfiguration",
                    "s3:DeleteBucketWebsite",
                    "s3:GetIntelligentTieringConfiguration",
                    "s3:GetObjectVersionAcl",
                    "s3:GetBucketPolicyStatus",
                    "s3:GetObjectRetention",
                    "s3:GetJobTagging",
                    "s3:ListJobs",
                    "s3:PutObjectLegalHold",
                    "s3:PutBucketCORS",
                    "s3:ListMultipartUploadParts",
                    "s3:GetObject",
                    "s3:DescribeJob",
                    "s3:PutBucketLogging",
                    "s3:GetAnalyticsConfiguration",
                    "s3:GetObjectVersionForReplication",
                    "s3:GetAccessPointForObjectLambda",
                    "s3:CreateAccessPoint",
                    "s3:GetAccessPoint",
                    "s3:PutAccelerateConfiguration",
                    "s3:SubmitMultiRegionAccessPointRoutes",
                    "s3:DeleteObjectVersion",
                    "s3:GetBucketLogging",
                    "s3:ListBucketVersions",
                    "s3:RestoreObject",
                    "s3:GetAccelerateConfiguration",
                    "s3:GetObjectVersionAttributes",
                    "s3:GetBucketPolicy",
                    "s3:PutEncryptionConfiguration",
                    "s3:GetEncryptionConfiguration",
                    "s3:GetObjectVersionTorrent",
                    "batch:*",
                    "s3:GetBucketRequestPayment",
                    "s3:GetAccessPointPolicyStatus",
                    "s3:GetObjectTagging",
                    "s3:GetBucketOwnershipControls",
                    "s3:GetMetricsConfiguration",
                    "s3:GetBucketPublicAccessBlock",
                    "sqs:ListQueues",
                    "s3:GetMultiRegionAccessPointPolicy",
                    "s3:GetAccessPointPolicyStatusForObjectLambda",
                    "s3:ListAccessPoints",
                    "s3:PutBucketOwnershipControls",
                    "s3:DeleteMultiRegionAccessPoint",
                    "s3:ListMultiRegionAccessPoints",
                    "s3:UpdateJobStatus",
                    "s3:GetBucketAcl",
                    "s3:ListStorageLensConfigurations",
                    "s3:GetObjectTorrent",
                    "s3:GetBucketLocation",
                    "s3:GetAccessPointPolicy",
                    "s3:ReplicateDelete"
                ],
                "Resource": "*"
            }
        ]
    }


    response = iam.create_policy(
                    PolicyName=twinflow_policy_name,
                    PolicyDocument= json.dumps(newPolicy),
                    Description="General permissions needed to run a TwinFlow L4 DT"
                    )

    return response['Policy']['Arn']


def create_instance_profile(iam, roleARN):
    try:
        name = roleARN.split('/')[-1]
        response = iam.create_instance_profile(
            InstanceProfileName=name
            )

        response2 = iam.add_role_to_instance_profile(
                        InstanceProfileName=name,
                        RoleName=name
                    )
    except Exception as e:
        if "EntityAlreadyExists" in str(e):
            print("Iam profile already exists.")
        else:
            raise e



#-------------------------------------------------------------
#%%
def create_twinflow_IAM_role(roleName:str) -> str:
    '''
    This function uses the SDK to create development
    IAM permissions.  This function is experimental and
    expected to be replaced by CDK.  Consider this deprecated.

    Parameters
    ----------
    roleName : str

    Returns
    -------
    roleARN

    '''


    iam = boto3.client("iam")

    roleARN, full_name = is_role_available(iam, roleName)
    if not roleARN:
        create_role(iam, roleName)
        roleARN, full_name = is_role_available(iam, roleName)
    else:
        attach_policies(iam, full_name)

    newARN = create_twinflow_policy(iam, roleARN)
    attach_policies(iam, full_name, single_policy = newARN)

    #create an instance profile and attach role to it
    create_instance_profile(iam, roleARN)

    return roleARN

