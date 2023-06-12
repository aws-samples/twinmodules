# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

import os
from tqdm import tqdm
from twinmodules.AWSModules.AWSBatch import batch
from twinmodules.AWSModules.AWS_S3 import s3_all_contents
from joblib import Parallel, delayed


#---------------------------------------------------------------------------------------------------

def autoscale_sensors(iam_role:str,
                      s3_bucket_name:str,
                      ansys_license_server:str="",
                      virtual_sensor_img:str = "",
                      cpu:int = 2,
                      memory:int=2048,
                      gpu:int=0,
                      s3_IoT_key:str = "DG-NG-sensor-data/" ) -> None:
    '''

    Automatically create or destroy virtual sensors in an AWS Batch environment.
    This function can be used with or without an ANSYS license server.

    1) A connection to the Batch compute environment is established.
    2) The general job definition for a virtual sensor is defined
    3) Existing running virtual sensors (i.e. existing Batch jobs) are queried
    4) New sensor is checked in an S3 Bucket

       Objects are assumed to be named:  <someName>_#.<csv>
       All of the object # are determined and assumed that a virtual sensor will
       be associated with each #.  If there is no virtual sensor from step 3
       associated with #, then a virtual sensor will be created.  If there is a
       virtual sensor and no associated #, then the sensor will be destroyed.

    5) Kill all sensors no longer associated with data.
    6) Create all new sensors that do not exist, but data is now available.


    Parameters
    ----------
    iam_role : str
        IAM rol to be assumed by virtual sensors.
    s3_bucket_name : str
        The s3 bucket to look for data.
        #TODO: will add connections to all other TwinModules data sources. For
        meta data determination.
    ansys_license_server : str, optional
        Use this license server ip address if applicable. The default is "".
    virtual_sensor_img : str, optional
        The container image to use (URL). The default is "".
    cpu : int, optional
        Required cpus needed for virtual sensor. The default is 2.
    memory : int, optional
        Required RAM in MB needed for virtual sensor. The default is 2048.
    gpu : int, optional
        Number of gpus needed by virtual sensor.  Note the AWS Batch compute
        environment must be able to support gpus. The default is 0.
    s3_IoT_key : str, optional
        The s3 key/folder to use for new data. The default is "DG-NG-sensor-data/".

    Returns
    -------
    None

    '''

    twin_batch = batch('ec2',  IAM_role = iam_role )

    jobDefinitionName = 'virtual-sensor-base_definition'
    job_command = ["python","virtual_sensor.py",
                   '-i',  "somefile.csv",
                   '-s',  s3_bucket_name,
                   '--ansys_server', ansys_license_server]

    #define the job command and the resource requirements for a single sensor
    twin_batch.defineBatchJob(virtual_sensor_img,
                              "",
                              job_command,
                              cpu,    #vCPU
                              memory, #RAM
                              jobDefinitionName,
                              gpu=gpu)

    #routine needed to enable multiprocessing
    def job_spin(input_data_file):
        train_i = input_data_file.split('_')[-1].split('.')[0]

        #setup the job and submit to batch
        job_command = ["python","virtual_sensor.py",
                       '-i',  s3_IoT_key+input_data_file,
                       '-s',  s3_bucket_name,
                       '--ansys_server', ansys_license_server]

        job = None
        print("jobname***********************************************")
        print('twinflow-batch-virtual-sensor-'+str(train_i))

        job = twin_batch.sendBatchJob('twinflow-batch-virtual-sensor-'+str(train_i),
                                      jobDefinitionName,
                                      override_command = job_command)
        return job['jobId']

    #are the sensors already running?
    running_jobs = twin_batch.get_running_jobs()

    running_id = []
    if running_jobs:
        #we only care about the virtual sensors in this block and not the
        #calibration, so filter that out
        #running_jobs = [x for x in running_jobs if 'calibration' not in x[0]]
        running_jobs = [x for x in running_jobs if 'virtual-sensor' in x[0]]
        running_id = [int(x[0].split('-')[-1]) for x in running_jobs]

    #incoming_sensor_data = s3_all_contents("DG-NG-sensor-data/", s3_bucket_name)
    incoming_sensor_data = s3_all_contents(s3_IoT_key, s3_bucket_name)
    idnum = [int(x.split('_')[-1].split('.')[0]) for x in incoming_sensor_data]

    #kill sensors if IoT data stops coming for that train
    deadjobs = [x for x in running_id if x not in idnum]
    if running_jobs:
        deadjobs = [x[1] for x in running_jobs if int(x[0].split('-')[-1]) in deadjobs]
        twin_batch.kill_jobs(deadjobs)

    #start a digital twin for each data object in the s3 bucket that is not already running
    newjobs = [os.path.basename(x) for x in incoming_sensor_data]
    newjobs = [newjobs[i] for  i,x in enumerate(idnum) if x not in running_id]
    Parallel(n_jobs=-1, backend='threading')(delayed(job_spin)(job_i)
                                                    for job_i in tqdm(newjobs))
