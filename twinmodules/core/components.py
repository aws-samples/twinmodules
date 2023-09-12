# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

#generic modules
import os
from tqdm import tqdm
from joblib import Parallel, delayed
import numpy as np
import platform
import shutil

#fmu modules
import fmpy
from fmpy.fmi2 import FMU2Slave
from fmpy import read_model_description


#twinflow modules
from twinmodules.AWSModules.AWSBatch import batch
from twinmodules.AWSModules.AWS_S3 import s3_all_contents
from twinmodules.core.util import is_steady_state
from twinmodules.AWSModules.AWS_secrets import get_secret
from twinmodules.AWSModules.AWS_S3 import get_data_s3
from twinmodules.core.sql_databases import SQLHandler


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


#------------------------------------------------------------------------------------------
#TODO: update docstring
def evaluate_data(X, config):

    twin_batch = batch('ec2',  IAM_role = '' )

    if isinstance(X, np.ndarray):
        if len(X.shape) == 1:
            X=[X]

    print("Submitting Jobs")
    for i, x in tqdm(enumerate(X)):
        job_command = ["python3.10",config['worker_script'],
                       "-x", ",".join(map(str,x)),
                       "-t",config['eval_table'],
                       "-i",config['uid'],
                       "-c",config['config_filename']]
        

        response = twin_batch.sendBatchJob(config['jobDefinitionName'] + '-'+str(i),
                                           config['jobDefinitionName'],
                                           override_command = job_command)

    print("Waiting for jobs to complete.")
    #wait for termination
    if len(X) > 1:
        running_jobs = twin_batch.get_running_jobs()
        running_ids = [x[1] for x in running_jobs]
    else:
        running_ids = [response['jobId']]

    twin_batch.wait_for_jobs_finish(running_ids)

#------------------------------------------------------------------------------------------

def run_transient(fmu, step_size, result_vrs, stop_time, ss_iterations, tolerance):
    time = 0.0
    nsteps = int( (stop_time - time )/step_size)
    times = np.linspace(time, stop_time, num =  nsteps )
    results = []
    watch = []
    for time in times:
        fmu.doStep(currentCommunicationPoint=time, communicationStepSize=step_size)
        result = fmu.getReal(result_vrs)

        results.append(result)
        tmp = np.array(results)
        #stopping simulation once all output variables have reached steady state
        #or we hit time limit
        watch = tmp / (tmp.max(axis=0)+1e-6)
        watch = np.mean(watch,axis=1)
        if is_steady_state(watch, last_n_values=ss_iterations, tolerance =tolerance):
            break
    return times, results, watch

#-----------------------------------------------------------------------------

#TODO: update docstring
def run_fmu(X0, config, table, uid, use_cloud = True):
    '''
    1) First download the FMU from remote source or local for it in local dir.
    2) Simulate with custom inputs
    3) Write to RDS to record results or return results in pandas dataframe

    '''

    fmu_filename = config['fmu_file']
    bucket_name = config["s3_bucket_name"]

    # download the FMU
    if use_cloud:
        get_data_s3(fmu_filename,  fmu_filename, bucket_name)
    else:
        if not os.path.isfile(fmu_filename):
            raise ValueError(f"ERROR: cannot find {fmu_filename} in the local "
                             +"file system.")

    # read the model description
    model_description = read_model_description(fmu_filename)

    # collect the value references for the variables to read / write
    vrs = {}
    for variable in model_description.modelVariables:
        vrs[variable.name] = variable.valueReference

    # extract the FMU
    unzipdir = fmpy.extract(fmu_filename)
    #if the fmu is not setup for linux, compile the linux binaries into the fmu
    if not os.path.isdir( unzipdir + "/binaries/linux64") and 'Windows' not in platform.platform():
        raise ValueError("ERROR: fmu is not setup for linux")
        #TODO: this needs more testing, for some reason if I do this manually, works great
        # but via python script, it throws errors
        os.system('fmpy compile {}'.format(fmu_filename))
        #extract again, now with binary
        unzipdir = fmpy.extract(fmu_filename)


    fmu_args = {'guid': model_description.guid,
                'modelIdentifier': model_description.coSimulation.modelIdentifier,
                'unzipDirectory': unzipdir}

    # determine the user defined inputs and outputs
    inputs = [config[x] for x in config.keys() if "input" in x
                                              and 'sample_' not in x
                                              and 'bounds_' not in x]
    outputs = [config[x] for x in config.keys() if "result" in x ]

    #convert to the fmu ids
    start_vrs = [vrs[x] for x in inputs]
    result_vrs = [vrs[x] for x in outputs]

    fmu = FMU2Slave(**fmu_args)
    fmu.instantiate()

    # get the start values for the current index
    #X0 = [0, 0, 0.2, 0, 0, 0, 0, 0.2, 0]
    start_values = X0

    fmu.reset()
    fmu.setupExperiment()

    # set the start values
    fmu.setReal(vr=start_vrs, value=start_values)

    fmu.enterInitializationMode()
    fmu.exitInitializationMode()


    step_size = config['fmu_step_size']
    stop_time = config['fmu_stop_time']
    iterations = config['fmu_ss_iterations']
    tolerance = config['fmu_ss_tolerance']

    try:
        times, results, watch = run_transient(fmu, step_size, result_vrs, stop_time,
                                              iterations, tolerance )
    except:
        print("Run failed reducing time step.")
        fmu.reset()
        #reduce step size one order of magnitude
        power = np.round(np.log(step_size)/np.log(10),0)
        new_step = 10**(power -1)
        times, results, watch = run_transient(fmu, new_step, result_vrs, stop_time,
                                              int(2*iterations),
                                              0.3*tolerance )
        #times, results, watch = run_transient(fmu, 1e-2, result_vrs, stop_time, 100, 3e-4)

    fmu.terminate()

    # call the FMI API directly to avoid unloading the share library
    fmu.fmi2FreeInstance(fmu.component)

    #clean up temp dir
    shutil.rmtree(unzipdir)

    #TODO: dev diagnostics, to be deleted
    if False:

        import matplotlib.pyplot as plot
        plot.close('all')
        results = np.array(results)
        watch = np.array(watch)

        plot.figure()
        plot.plot(times[:results.shape[0]], watch)
        plot.ylabel('watch (N)')
        plot.xlabel('Time (s)')

        for i, output in enumerate(outputs):
            if 'SlipVelocity' in output:
                plot.figure()
                plot.plot(times[:results.shape[0]], results[:,i])
                plot.ylabel(output)
                plot.xlabel('Time (s)')
                plot.tight_layout()

        for i, output in enumerate(outputs):
            if 'Pa' in output:
                plot.figure()
                plot.plot(times[:results.shape[0]], results[:,i])
                plot.ylabel(output)
                plot.xlabel('Time (s)')
                plot.tight_layout()

        for i, output in enumerate(outputs):
            if 'Roller9' in output:
                if 'SlipVelocity' in output:
                    print(results[-1,i])
                plot.figure()
                plot.plot(times[:results.shape[0]], results[:,i])
                plot.ylabel(output)
                plot.xlabel('Time (s)')
                plot.tight_layout()

        for i, output in enumerate(outputs):
            if 'deg' in output:
                plot.figure()
                plot.plot(times[:results.shape[0]], results[:,i])
                plot.ylabel(output)
                plot.xlabel('Time (s)')
                plot.tight_layout()

    #format the results
    results = np.array(results)
    #use only steady state results
    results = results[-1,:]

    final_columns = inputs + outputs
    final_data = np.concatenate((X0,results))

    #not a lot of meaning at the moment
    final_columns.append("batch")
    final_columns.append("eval_id")
    final_data = np.concatenate((final_data,[0],[int(uid)]))

    if use_cloud:
        secret = get_secret(config['secret_name'], config['region_name'])
        with SQLHandler(secret, config['mysql_db_endpoint'], config['database_name']) as sql:
            sql.send_sql_data(table, final_columns,  [final_data] )
    else:
        import pandas
        final = pandas.DataFrame(final_data)
        final = final.T
        final.columns = final_columns
        return final