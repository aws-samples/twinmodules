# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

from twinmodules.core.util import get_user_data
from joblib import Parallel, delayed
import os
import boto3
import docker
import base64
import re
import numpy as np

try:
    dockerClient = docker.from_env()
    docker_api = docker.APIClient()
except:
    print("ERROR: Docker is not installed on this system.")



def _ecr_login(region):

    client = boto3.client('ecr', region_name=region)

    token = client.get_authorization_token()
    username, password = base64.b64decode(token['authorizationData'][0]['authorizationToken']).decode().split(':')
    #registry = token['authorizationData'][0]['proxyEndpoint']
    auth_config_payload = {'username': username, 'password': password}

    return auth_config_payload

#------------------------------------------------------------------------------------

def _docker_build( docker_file, tagname):
    #https://docker-py.readthedocs.io/en/1.2.3/api/
    path = os.path.dirname(docker_file)
    for line in docker_api.build( path = path,
                                  dockerfile  = docker_file,
                                  tag = tagname,
                                  rm=False):
        reline = _clean_text_log(line)
        print(reline)
        #error check
        if "errorDetail" in reline:
            raise ValueError("ERROR: during docker build.")

#------------------------------------------------------------------------------------

def _add_ecr_tag_to_repo( tagname, account_number, region):
    repo_name = "{1}.dkr.ecr.{2}.amazonaws.com/{0}".format(tagname, account_number, region)
    image_name = "{0}:latest".format(tagname)
    dockerClient.images.get(image_name).tag(repository=repo_name, tag='latest')

#------------------------------------------------------------------------------------

def _push_to_ecr(auth_config_payload, account_number,region, tagname):
    repo_name = "{1}.dkr.ecr.{2}.amazonaws.com/{0}".format(tagname, account_number, region)
    for line in docker_api.push( repo_name,
                                 'latest',
                                 stream=True,
                                 auth_config=auth_config_payload ):
        reline = _clean_text_log(line)
        print(reline)





#------------------------------------------------------------------------------------

def _clean_text_log(line):
    '''
    Docker api log has a bunch of extra characters making it difficult to read.
    This function cleans off the extra bits.
    '''
    linedecode = line.decode("utf-8")
    reline = re.findall(r'(?<=stream":)(.*)(?=})', linedecode)
    if len(reline)==0:
        reline = re.findall(r'(?<={)(.*)(?=})', linedecode)
    reline = np.squeeze(reline).item()
    reline = reline.replace("\\n", '')
    return reline

#------------------------------------------------------------------------------------



def _build_and_push(docker_file, tagname, account_number, region):

    #default is multiprocessing and not threading, so dir change should be fine
    location = os.path.dirname(docker_file)
    os.chdir(location)

    auth_config_payload = _ecr_login(region)

    _docker_build( docker_file, tagname)

    _add_ecr_tag_to_repo( tagname, account_number, region)

    _push_to_ecr(auth_config_payload, account_number,region, tagname)

#------------------------------------------------------------------------------------

def _repo_exist(repo):
    client = boto3.client('ecr')
    response = client.describe_repositories()
    response['repositories']
    for meta in response['repositories']:
        if repo in meta['repositoryName']:
            return True
    return False

#------------------------------------------------------------------------------------

def _create_repo(repo_name):
    client = boto3.client('ecr')
    client.create_repository(repositoryName=repo_name)


#------------------------------------------------------------------------------------

def containerize(region:str,
                 files_to_process:list[dict],
                 n_jobs:int = 1)-> None:
    '''

    Function enables parallel containerization of several docker files and will
    push to ECR when completed. If the ECR container repo does not exist,
    TwinModules will attempt to create.  Note this assumes users have proper
    IAM access and will auto login into ECR for tagging and pushing.

    This function call can also be called from the CLI for quick building and pushing
    of containers. E.g.

    .. code-block:: bash

        python tfcli.py -bp --region us-east-1 -d ./mydockerfile -t mydocker

    Here an ECR repo will be looked for or created in the us-east-1 region, the
    mydockerfile will be used to create the container and the tag my docker will be
    used for naming the container and the ECR repo.

    Parameters
    ----------
    region : str
        AWS region.
    files_to_process : list[dict]
        Expecting a list of dictionaries. Where the key is the repo name
        and the value is the location of the docker file.

        Example:
            files_to_process = [
                {'gpu-worker': '/home/ubuntu/projects/twinflow/examples/Dockerfile-gpu-worker'}
                ]

    n_jobs : int, optional
        Number of cpu to use. The default is 1.

    Returns
    -------
    None

    '''

    #convert json input from list[dict] to dict
    repo_info = {}
    if isinstance(files_to_process, list):
        for ele in files_to_process:
            repo_info[list(ele.keys())[0]] = list(ele.values())[0]

    #check if repo exists
    existance = {repo:_repo_exist(repo) for repo in repo_info.keys()}
    for repo, exist in existance.items():
        if not exist:
            _create_repo(repo)

    user_data = get_user_data()
    account_number = user_data['Account']

    Parallel(n_jobs=n_jobs)(delayed(_build_and_push)(repo_info[tagname], tagname, account_number, region)
                     for tagname in repo_info.keys())













