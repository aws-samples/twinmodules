# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

import awswrangler as wr
import pandas
import boto3

class timestream(object):
    '''

        **Deprecated:** AWS Wrangler now includes all of these features.


        Auto-setup SQL queries and utilize the awswrangler package
        to submit/query pandas dataframes to AWS Timestream database.

        If tables or database do not exist, they will be
        automatically generated.

    '''

    def __init__(self,  database:str,
                        table:str ):
        '''


        Parameters
        ----------
        database : str
            Name of timestream database
        table : str
            Table in the timestream database.

        Returns
        -------
        None.

        '''
        self.database = database
        self.table = table

        #if user supplied values dont exist, create them
        self.client = boto3.client('timestream-write')
        if not self._database_exist():
            wr.timestream.create_database(database)
        if not self._table_exist():
            wr.timestream.create_table(database, table,
                                       memory_retention_hours=24,
                                       magnetic_retention_days=30)

    def _database_exist(self):

        try:
            self.client.describe_database(
                            DatabaseName=self.database )
        except Exception as e:
             if "ResourceNotFoundException" in str(e):
                 return False
             else:
                 raise e
        return True

    def _table_exist(self):
        try:
            self.client.describe_table(
                            DatabaseName=self.database,
                            TableName=self.table
                            )
        except Exception as e:
             if "ResourceNotFoundException" in str(e):
                 return False
             else:
                 raise e
        return True

    def delete_database(self) -> None:
        '''
        Delete the timestream database.

        Returns
        -------
        None
            DESCRIPTION.

        '''
        all_tables = self.client.list_tables(
                            DatabaseName=self.database)

        all_tables = [x['TableName'] for x in all_tables['Tables']]
        for table in all_tables:
            wr.timestream.delete_table(self.database, table)
        wr.timestream.delete_database(self.database)


    def delete_table(self, table:str=None) -> None:
        '''
        Delete a table within the timestream database.

        Parameters
        ----------
        table : str, optional
            Name of table to delete. Will use the intial table
            name during object instantiation, if none provide here.
            The default is None.

        Returns
        -------
        None

        '''
        if table is None:
            wr.timestream.delete_table(self.database, self.table)


    def send_data(self, data: pandas.DataFrame,
                        time_col: str,
                        primary_col: list[str],
                        secondary_col:list[str]=[],
                             ) -> None:
        '''

        Send data to an AWS Timestream database.

        Parameters
        ----------
        data : pandas.DataFrame
            Data to be inserted into Timestream database
        time_col : str
            This data should be interpreted as time.  This must be
            a datetime formated value.
        primary_col : list
            These columns will be automatically assumed to be floats or ints
            in the timestream schema.
        secondary_col : list, optional
            These columns will be automatically assumed to be char
            in the timestream schema.
            The default is [].

        Returns
        -------
        None

        '''


        if time_col not in data.columns                             \
            or any([x not in data.columns for x in primary_col])    \
            or any([x not in data.columns for x in secondary_col]):
                raise ValueError("ERROR: values in time_col, primary_col, secondary_col must"
                                 +" match columns in the dataframe.")

        if len(secondary_col)==0:
            secondary_col = primary_col

        rejected_records = wr.timestream.write(
            df=data,
            database=self.database,
            table=self.table,
            time_col=time_col,
            measure_col=primary_col,
            dimensions_cols=secondary_col
            )

        if len(rejected_records) > 0:
            raise ValueError("ERROR: Unable to submit all timestream records.")



    def get_data(self, most_recent:str = None,
                       limit:int = None,
                       time_col:str='time'
                       ) -> pandas.DataFrame:
        '''
        Submits an SQL query to Timestream to obtain all
        data from the database

        .. code-block:: bash

            SELECT * FROM "{database}"."{table}"


        Parameters
        ----------
        most_recent : string, optional
            Provide an sql understandable time limit
            such as 15m, 24h, etc.  The default is None.
        limit : int, optional
            Limit the sql response to N number of
            entries. The default is None.

        Returns
        -------
        query_data : pandas.DataFrame
            Result of SQL query.
        '''


        query = 'SELECT * FROM ' + f'"{self.database}".' \
                +f'"{self.table}"'

        if most_recent is not None:
            query += f" WHERE {time_col} between ago({most_recent}) and now()"

        if limit is not None:
            query += f" LIMIT {limit}"


        print(query)
        query_data = wr.timestream.query(query)
        return query_data















