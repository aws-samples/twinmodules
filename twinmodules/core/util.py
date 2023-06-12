# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

import json
import boto3
import os
import pandas
import numpy as np


from twinmodules.AWSModules.AWS_S3 import s3_all_contents, get_data_s3
from twinmodules.AWSModules.AWS_secrets import get_secret
from twinmodules.core.sql_databases import SQLHandler



#-------------------------------------------------------------------------------------

def get_user_json_config(filename:str) -> dict:
    '''
    Read a json file and return as dictionary

    Parameters
    ----------
    filename : str

    Returns
    -------
    dict

    '''
    with open(filename,'r') as f:
        config = json.load(f)
    config['config_filename'] = filename
    return config

#-------------------------------------------------------------------------------------

def get_user_data() -> dict:
    '''
    Get the user metadata.

    Returns
    -------
    user : dict

    '''
    client = boto3.client('sts')
    user = client.get_caller_identity()
    return user


#-------------------------------------------------------------------------------------

# TODO: is this really needed, only usefuly when called from container,
# container could be modded to eliminate this need
# probably delete this
def sqs_wait(*args, **kwargs) -> str:
    '''
    Deprecated.
    '''
    import sys
    sys.path.append('/wd')
    from twinmodules.AWSModules.AWS_SQS import watch_sqs

    newfiles = watch_sqs(*args, **kwargs)
    return newfiles


#-------------------------------------------------------------------------------------

def get_calibration_data(folder_name:str, s3_bucket_name:str) -> list[str]:
    '''
    Download to local file system all data in a folder of an
    s3 bucket.

    Parameters
    ----------
    folder_name : str
        The s3 bucket key
    s3_bucket_name : str

    Returns
    -------
    list[str]
        List of all the files downloaded.

    '''
    all_files = s3_all_contents(folder_name, s3_bucket_name)
    calibration_files = []
    for file_to_get in all_files:
        basename = os.path.basename(file_to_get)
        get_data_s3(basename, file_to_get, s3_bucket_name)
        calibration_files.append(basename)
    return calibration_files

#-------------------------------------------------------------------------------------

def setup_uncertainty_propagation_db(config:dict,
                                     delete_existing_table = False,
                                     delete_existing_db = False) -> None :
    '''
    Setup an SQL database with several tables needed to store
    the results of the uncertainty progation from twinstat.

    The schema will use the following column names:
        batch int
        eval_id int

        The config input dict will be reviewed and all keys that
        contain the words 'input' or 'result' will be used as
        column names with the double datatype.


    Requires proper IAM role that enables modification of
    the SQL databased in the 'mysql_db_endpoint'

    Tables are produced:

        Example:
            .. code-block:: python

                config = {
                    'input_0': "sprocket_1",
                    'input_1': "sprocket_2",
                    'output_0': "flowrate_12"
                    'output_1': "flowrate_14"
                    }

        'uncertainty_propagation_samples',

            The config input dict will be reviewed and all keys that
            contain the words 'input' or 'result' will be used as
            column names with the double datatype.

            Example Schema:
                .. code-block:: python

                    [
                        'batch int',
                        'eval_id int',
                        'sprocket_1 double',
                        'sprocket_2 double',
                        'flowrate_12 double'
                        'flowrate_14 double'
                    ]

        'uncertainty_propagation_pdf',

            Example Schema:
                .. code-block:: python

                    [
                        'flowrate_12_xtest double',
                        'flowrate_12_pdf double',

                        'flowrate_14_xtest double',
                        'flowrate_14_pdf double'
                    ]

        'uncertainty_propagation_cdf',

            Example Schema:
                .. code-block:: python

                    [
                        'flowrate_12_xtest double',
                        'flowrate_12_cdf double',

                        'flowrate_14_xtest double',
                        'flowrate_14_cdf double'
                    ]

        'uncertainty_propagation_sensitivity'

            Example Schema:
                .. code-block:: python

                    [
                        'output_variable tinytext',
                        'sprocket_1 double',
                        'sprocket_2 double',
                    ]


    Parameters
    ----------
    config : dictionary
        Inputs provided from the user json file.
    delete_existing_table : bool, optional
        If the table exists, delete it from the database.
        The default is False.
    delete_existing_db : bool, optional
        If the database exists attempt to delete, although this may
        not delete if there are other active connections to the
        database. A warning will be thrown if this occurs.
        The default is False.

    Returns
    -------
    None.

    '''


    #delete previous database, setup new tables
    secret = get_secret(config['secret_name'], config['region_name'])
    with SQLHandler(secret, config['mysql_db_endpoint'], config['database_name']) as sql:
        #sql = SQLHandler(secret, config['mysql_db_endpoint'], config['database_name'])
        if delete_existing_db:
            sql.delete_db()
        sql.create_db()
        #reconnect to new database
        sql.connect()

        tables = ['uncertainty_propagation_samples',
                  'uncertainty_propagation_pdf',
                  'uncertainty_propagation_cdf',
                  'uncertainty_propagation_sensitivity']

        if delete_existing_table:
            for table in tables:
                #delete previous table data since we are doing a new run
                sql.delete_sql_data_table(table)

        #need a list the includes the batch number and all inputs and outputs
        columns = ['batch int', 'eval_id int']
        inputs_outputs = [config[x] + " double" for x in config.keys() if ("input" in x or "result" in x) and 'sample_' not in x]
        columns.extend(  inputs_outputs )
        #setup the sampling and results table
        sql.create_table( tables[0], columns)

        #setup a table to hold the pdf
        outputs = [config[x] for x in config.keys() if "result" in x]
        #add the _xtest or __pdf suffix
        xt = [x+'_xtest' for x in outputs]
        pdf = [x+'_pdf' for x in outputs]
        fc = xt + pdf
        columns = [x + " double" for x in fc]
        sql.create_table(tables[1], columns)

        #setup a table to hold the cdf
        #add the _xtest or __cdf suffix
        cdf = [x+'_cdf' for x in outputs]
        fc = xt + cdf
        columns = [x + " double" for x in fc]
        sql.create_table(tables[2],columns)

        #setup table to hold the sensitivity results
        columns = ['output_variable tinytext']
        inputs = [config[x] + " double" for x in config.keys() if "input" in x and 'sample_' not in x]
        columns.extend(  inputs )
        sql.create_table( tables[3], columns)

        tables = sql.get_tables()
        print("Tables created in {} are: ".format(config['database_name']))
        print(tables)


#-------------------------------------------------------------------------------------

def setup_sql_db(config:dict,
                 table_name:str,
                 delete_existing_table:bool = False,
                 delete_existing_db:bool = False) -> None :

    '''
    Setup an SQL database.

    The schema will use the following column names:
        batch int
        eval_id int

        The config input dict will be reviewed and all keys that
        contain the words 'input' or 'result' will be used as
        column names with the double datatype.


    Example:
        .. code-block:: python
            config = {
                'input_0': "sprocket_1",
                'output_0': "flowrate_14"
                }

        Schema:
            .. code-block:: python

                [
                    'batch int',
                    'eval_id int',
                    'sprocket_1 double',
                    'flowrate_14 double'
                ]


    Requires proper IAM role that enables modification of
    the SQL databased in the 'mysql_db_endpoint'


    Parameters
    ----------
    config : dictionary
        Inputs provided from the user json file.
    table_name : str
    delete_existing_table : bool, optional
        If the table exists, delete it from the database.
        The default is False.
    delete_existing_db : bool, optional
        If the database exists attempt to delete, although this may
        not delete if there are other active connections to the
        database. A warning will be thrown if this occurs.
        The default is False.

    Returns
    -------
    None.

    '''

    #delete previous database, setup new tables
    secret = get_secret(config['secret_name'], config['region_name'])
    with SQLHandler(secret, config['mysql_db_endpoint'], config['database_name']) as sql:

        if delete_existing_db:
            sql.delete_db()
        sql.create_db()
        #reconnect to new database
        sql.connect()

        tables = [table_name]

        if delete_existing_table:
            for table in tables:
                #delete previous table data since we are doing a new run
                sql.delete_sql_data_table(table)

        #need a list the includes the batch number and all inputs and outputs
        columns = ['batch int', 'eval_id int']
        inputs_outputs= []
        for x in config.keys():
            if isinstance(config[x], list):
                continue
            if ("input" in x or "result" in x) and 'sample_' not in x:
                inputs_outputs.append(config[x] + " double"  )
        columns.extend(  inputs_outputs )
        #setup the sampling and results table
        sql.create_table( tables[0], columns)

        tables = sql.get_tables()
        print("Tables created in {} are: ".format(config['database_name']))
        print(tables)

#-------------------------------------------------------------------------------------

def is_steady_state(input_signal:np.array,
                    last_n_values:int = 100,
                    method:str = 'relative',
                    tolerance:float = 0.0):
    '''
    Check if the incoming signal has stopped moving and reached a constant value.

    Determination made by regressing the last 'last_n_values' on time
    and calculating the probability the linear coefficient is different from
    'signal_magnitude_relevance'. If 'signal_magnitude_relevance' is not
    provided, zero is assumed.

    If it is different from zero, the signal has not reached
    steady state and False is returned.

    Example:  If we have very noisy temperature it may be difficult
    to determine exactly when it is steady state, but we also maybe only care
    about temperature increases above 1deg.  Thus, use 'signal_magnitude_relevance'=1.0
    and steady will only be True if the signal is changing at a rate of 1deg/s or less.


    Parameters
    ----------
    input_signal : np.array
        Signal to check for steady state.
    last_n_values : int, optional
        Only include this number of data points in the regression. The default is 100.
    method : str, optional
        'statistical' or 'relative'
        The default is 'relative.

        'statistical' uses the moving linear regression to
        compensate for noise

        'relative' uses the average relative change in the signal

    tolerance : float, optional
        Size of statistical coefficient needed to be relevant.
        Or the average relative change.
        The default is 0.0.

    Returns
    -------
    bool
        If True, the signal is steady state.

    '''

    input_signal = np.array(input_signal)

    from twinstat.core.LinearRegression import Polynomial


    if input_signal.shape[0] < last_n_values:
        return False

    signal = input_signal[-last_n_values:]
    if method == 'statistical':
        time = np.arange(signal.shape[0])
        #just want to check a straight line, using small data so dont need gpu
        line = Polynomial(1, backend='numpy')
        line.fit(time, signal, beta_relevance = [0,tolerance])

        if line.beta_pvalues[1] < 0.05:
            return False
        else:
            return True
    else:
        diff = np.diff(input_signal)/input_signal[1:]
        avg_diff = np.mean(np.abs(diff))
        if avg_diff < tolerance:
            return True
        else:
            return False

    # plot.figure()
    # plot.scatter(range(input_signal.shape[0]),input_signal)
    # plot.scatter(time,signal)
    # plot.plot(time, line.predict(time))









#-------------------------------------------------------------------------------------