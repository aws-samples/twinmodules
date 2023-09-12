# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

import boto3
import pandas
import numpy as np
from tqdm import tqdm
from datetime import datetime
import time

#TODO: Update doc strings for entire module

def get_asset_propert_id(name:str, assetId:str=None, region_name:str='us-east-1') -> str and str and str:
    '''
    Obtain the asset property ID.  If the sitewise database only includes
    one asset or uses uniquely named properties, the asset ID is not a
    required input.

    Parameters
    ----------
    name : str
        Name of the property a user wants data for.
    assetId : str, optional
        The asset ID that the user wants the data from.
        The default is None.


    Returns
    -------
    str and str and str
        asset_property_name, assetId, propertyId

    '''

    iot_sw_client = boto3.client('iotsitewise', region_name=region_name)

    available_timeseries = iot_sw_client.list_time_series()
    found = False

    if assetId is not None:
        response = iot_sw_client.describe_asset(
                        assetId=assetId)

        for prop in response['assetProperties']:
            if name.lower() == prop['name'].lower():
                asset_property_name = prop['name']
                propertyId = prop['id']
                found = True
                break

    else:
        for series in available_timeseries['TimeSeriesSummaries']:
            if found:
                break
            response = iot_sw_client.describe_asset(
                            assetId=series['assetId'])

            assetId = series['assetId']

            for prop in response['assetProperties']:
                if name.lower() == prop['name'].lower():
                    asset_property_name = prop['name']
                    propertyId = prop['id']
                    found = True
                    break

    if not found:
        raise ValueError(f"ERROR: could not find {name} in asset data")
    return asset_property_name, assetId, propertyId


#---------------------------------------------------------------------------

def get_asset_property_data(name:str, assetId:str=None,
                            maxResults:int=100,
                            region_name:str='us-east-1') -> pandas.DataFrame:
    '''
    Get the data for a specific property .If the sitewise database only includes
    one asset or uses uniquely named properties, the asset ID is not a
    required input.

    Parameters
    ----------
    name : str
        Measurement name / property name
    assetId : str, optional
        If the name is unique, no assetId needs to be specified, but there are multiple
        assets with identical property names, the assetId is required. The default is None.
    maxResults : int, optional
         The default is 100.

    Returns
    -------
    pandas.DataFrame
        [time, value]
    '''

    iot_sw_client = boto3.client('iotsitewise', region_name=region_name)
    
    #name = 'RPM'
    asset_property_name, assetId, propertyId = get_asset_propert_id(name, assetId=assetId)

    data = []
    paginator = iot_sw_client.get_paginator('get_asset_property_value_history')
    for response in paginator.paginate(assetId=assetId,
                                       propertyId=propertyId,
                                       timeOrdering='DESCENDING',
                                        PaginationConfig={
                                            'MaxItems': maxResults,
                                            }
                                       ):
        #print(response )
        tmp = [ [x['value']['doubleValue'], x['timestamp']['timeInSeconds']]
                        for x in response['assetPropertyValueHistory']]
        data.extend(tmp)


    if len(data) ==0:
        return pandas.DataFrame()
    data = pandas.DataFrame(data)
    data.columns = ['value', 'time']
    #standard is to have temporal ascending
    data = data.sort_values(by=['time']).reset_index(drop=True)
    return data


#---------------------------------------------------------------------------
def send_asset_property_data(name:str,
                             data_time:list or np.array,
                             data:list or np.array,
                             assetId:str=None,
                             ensure_time_contrain:bool=True,
                             use_current_time:bool=True,
                             use_time:float=0.0,
                             region_name:str='us-east-1'
                             ) -> None:
    '''

    Send up data into a specific asset propety.

    If the sitewise database only includes
    one asset or uses uniquely named properties, the asset ID is not a
    required input.

    Note that currently AWS IoT Sitewise only allows for 100 data points
    per second upload rate.

    Parameters
    ----------
    name : str
        Measurement name / property name
    data_time : list or np.array
        Time data in seconds.
    data : list or np.array
        Measurement data.
    assetId : str, optional
        If the name is unique, no assetId needs to be specified, but there are multiple
        assets with identical property names, the assetId is required. The default is None.
    ensure_time_contrain : bool, optional
        AWS Sitewise requires that the time value be within 604800 seconds before and
        600 seconds after the current timestamp in seconds.  This optional will shift
        the provided time to meet this contraint.

        Example:
            time = [1, 2, ...100]
            shift = current_time - time[0]
            updated_time = time + shift

    Returns
    -------
    None

    '''

    iot_sw_client = boto3.client('iotsitewise', region_name=region_name)

    data = np.array(data)
    data_time = np.array(data_time)

    asset_property_name, assetId, propertyId = get_asset_propert_id(name, assetId=assetId)

    if ensure_time_contrain:
        if use_current_time:
            dt = datetime.today()
            now = dt.timestamp()
        else:
            now = use_time
        shift = now - data_time[-1]
        data_time += shift

    #sitewise api only allows 10 enteries at a time
    n_chunks = int(np.ceil(data.shape[0]/10))
    insertion_data = []
    for chnk in range(n_chunks):
        propertyValues=[]
        #sitewise api allows 10 values per entry
        for i in range(10):
            if chnk*10+i >= data.shape[0]:
                continue
            propertyValues.append(
                {
                    'value': {
                        'doubleValue': data[chnk*10+i]
                        },
                    'timestamp': {
                        'timeInSeconds': int(data_time[chnk*10+i])
                        }
                    }
                )

        insertion_data.append(
                            {
                            'entryId': str(chnk),
                            'assetId':assetId,
                            'propertyId':propertyId,
                            'propertyValues':propertyValues
                            })



    #sitewise can only handle 10 enteries per push
    for i in tqdm(range(0,len(insertion_data), 10)):
        #finally push up to sitewise
        response  = iot_sw_client.batch_put_asset_property_value(entries=insertion_data[i:i+10])
        time.sleep(1.0)

        if 'errorEntries' in response.keys():
            if len(response['errorEntries']) > 0:
                if response['errorEntries'][0]['errors'][0]['errorCode'] == 'ThrottlingException':
                    raise ValueError("ERROR: could not insert data due to too many insertion requests.")
                else:
                    print(response)
                    raise ValueError("ERROR: could not insert data into sitewise.")




#---------------------------------------------------------------------------
def delete_asset_property_data(name:str,
                               assetId:str=None,
                               region_name:str='us-east-1'
                               ) -> None:
    '''
    Delete the existing data for a property.

    If the sitewise database only includes
    one asset or uses uniquely named properties, the asset ID is not a
    required input.

    Parameters
    ----------
    name : str
        Name of the property to be deleted.
    assetId : str, optional
        The specific asset to delete the data from.
        The default is None.

    Returns
    -------
    None

    '''

    iot_sw_client = boto3.client('iotsitewise', region_name=region_name)

    asset_property_name, assetId, propertyId = get_asset_propert_id(name, assetId=assetId)

    try:
        response = iot_sw_client.delete_time_series(
                                    assetId=assetId,
                                    propertyId=propertyId )
    except Exception as e:
        if "does not associate" in str(e):
            print(f"Data stream not found in AWS Sitewise for {name}  {assetId}")
        else:
            raise e



#%% main
if __name__ == '__main__':

    #testing with cookie facotry
    mdot1 = get_asset_property_data('flowrate1')
    mdot2 = get_asset_property_data('flowrate2')

    #made a new asset testing
    rpm = get_asset_property_data('rpm', assetId = '7e305d69-ad67-4e51-9ea2-2a763d9711ad')

    rpm = np.random.normal(size=15)
    import datetime
    import time
    times = []
    for _ in range(15):
        times.append(
            (datetime.datetime.now()-datetime.datetime(1970,1,1)).total_seconds()
            )
        time.sleep(1)


    send_asset_property_data('rpm',
                             times, rpm,
                             assetId = '7e305d69-ad67-4e51-9ea2-2a763d9711ad'
                             )