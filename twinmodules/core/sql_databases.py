# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

#note that pymysql is used over boto3 since boto3 only support aws aurora v1 and nothing else (currently)
import pymysql
import numpy as np
import pandas
import re
from twinmodules.AWSModules.AWS_secrets import get_secret


class SQLHandler(object):
    '''
    Enables managing data in a mysql database such
    as AWS RDS cloud service.

    Example use:

    .. code-block:: python

        secret = get_secret(config['secret_name'], config['region_name'])

        with SQLHandler(secret, config['mysql_db_endpoint'], config['database_name']) as sql:
            sql.create_db()
            #reconnect to new database
            sql.connect()

    '''

    def __init__(self, secret:dict, mysql_db_endpoint:str, database:str):
        '''


        Parameters
        ----------
        secret : dict
            Contains the username and password needed for database access.
        mysql_db_endpoint : str
            Location of the database
        database : str
            The name of the database to connect with.  If the database does
            not exist, the object will create the database and
            restablish connection specificaly to the database.

        Returns
        -------
        None.

        '''
        self.host = mysql_db_endpoint
        self.secret = secret
        self.database = database
        self.connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()

    def database_exist(self) -> bool:
        '''
        Check if the database exists.

        Returns
        -------
        bool
            If true the database exists.

        '''
        try:
            cursor = self.connection.cursor()
            cursor.execute("use {}".format(self._sanitize(self.database)))
            cursor.close()
            return True
        except pymysql.Error as e:
            if e.args[0] == 1049:
                return False
            else:
                raise

    def connect(self) -> None:
        '''
        Establish connection to the database.

        Returns
        -------
        None.

        '''
        if self.connection:
            self.connection.close()
        self._connect(True)
        if not self.database_exist():
            self.create_db()
            self.connection.close()
            self._connect(False)
        else:
            self.connection.close()
            self._connect(False)

    def _connect(self, nodb:bool):
        if nodb:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.secret["username"],
                password=self.secret["password"])
        else:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.secret["username"],
                password=self.secret["password"],
                db=self.database)

    def _open_database_connections(self):
        try:
            cursor = self.connection.cursor()
            cursor.execute("show processlist")
            processes = cursor.fetchall()
            cursor.close()

            for process in processes:
                if process[3] != 'Sleep':
                    return True
            return False
        except pymysql.Error as e:
            print(f"ERROR: {e}")
            return False

    def _kill_existing_connections(self):
        try:
          cursor = self.connection.cursor()
          cursor.execute("show processlist")
          processes = cursor.fetchall()
          for process in processes:
              if process[0] != self.connection.thread_id():
                  cursor.execute(f"kill {process[0]}")
          self.connection.commit()
          cursor.close()
        except pymysql.Error as e:
            if 'Unknown thread' not in str(e):
                print(f"ERROR: {e}")


    def _sanitize(self, string):
        return re.sub('[^a-zA-Z]+', '', string)

    def create_db(self) -> None:
        '''
        Create the database if it does not exist.

        Returns
        -------
        None.

        '''

        cursor = self.connection.cursor()
        cursor.execute("select version()")

        try:
            sql = 'create database {}'.format(self._sanitize(self.database))
            cursor.execute(sql)
            cursor.connection.commit()
        except Exception as e:
            if "database exists" in str(e):
                print(" Database already exists.")
            else:
                raise e
        cursor.close()


    def delete_db(self) -> None:
        '''
        Attempt to delete the database, but will
        gracefully exit if there are existing
        connections to the database.

        Returns
        -------
        None.

        '''
        # if self._open_database_connections():
        #     print("ERROR: Cannot delete database due to open connections.")
        #     return None
        self._kill_existing_connections()
        cursor = self.connection.cursor()
        try:
            sql = 'drop database {}'.format(self._sanitize(self.database))
            cursor.execute(sql)
            cursor.connection.commit()
        except Exception as e:
            if "database doesn't exist" in str(e):
                print(" Database doesnt exist.")
            else:
                raise e
        cursor.close()


    def create_table(self, table_name:str, columns:list[str]) -> None:
        '''
        Create a table with the schema define by the 'columns'.
        The unique table key labeled as (id)

        Parameters
        ----------
        table_name : str
        columns : list[str]
            List of sql schema strings such as:

                columns = [
                            'batch int',
                            'flowrate double'
                    ]

        Returns
        -------
        None

        '''

        cleaned_col = ', '.join(columns)
        cleaned_col = cleaned_col.replace("'", "''")

        cursor = self.connection.cursor()
        #Create a table
        sql = ' create table {} ( id int not null auto_increment, {}, primary key (id) )'.format(
                                                    self._sanitize(table_name), cleaned_col )
        try:
            cursor.execute(sql)
            cursor.connection.commit()
        except Exception as e:
            if "already exists" in str(e):
                print(" Table already exists.")
            else:
                raise e
        cursor.close()


    def get_tables(self) -> list:
        '''
        Returns a list of all the tables in the
        specified database.

        Returns
        -------
        list
            Table names

        '''
        cursor = self.connection.cursor()
        sql = '''show tables'''
        cursor.execute(sql)
        tables = cursor.fetchall()
        cursor.close()
        return tables

    def send_sql_data(self, table_name:str, columns:list[str], data:list) -> None:
        '''
        Insert the data provided in the 'data' list into the SQL table.
        The function will batch submit data.

        Parameters
        ----------
        table_name : str
        columns : list[str]
            Columns in the SQL database which correspond to the columns
            provied in 'data'
        data : list
            List of data of anytype and is converted to string before
            inserted into the SQL database

        Returns
        -------
        None

        '''

        cursor = self.connection.cursor()

        if not isinstance(columns, list):
            columns = [columns]

        ncol = len(columns)
        str_app = ''
        for _ in range(ncol):
            str_app+='%s,'
        str_app=str_app[:-1] #get rid of trailing comma
        query = ''' insert into {}({}) values({})'''.format(self._sanitize(table_name), ','.join(columns) , str_app  )

        data_insert = []
        for d in data:
            if not isinstance(d, list) and not isinstance(d, np.ndarray):
                d = [d]
            #need to add quotes around any strings in the dataset
            d = [f'"{x}"' if isinstance(x,str) else x for x in d ]
            #then convert entire set to an sql query string
            d = list(map(str,d))
            data_insert.append( tuple(d) )

        cursor.executemany(query, data_insert)
        self.connection.commit()
        cursor.close()


    def delete_sql_data_table(self, table_name:str,
                                    delete_table:bool = True) -> None:
        '''
        Delete all data in the table.  The table itself will not
        be deleted unless specified.

        Parameters
        ----------
        table_name : str
        delete_table : bool, optional
            Also delete the table in addition to the data.
            The default is True.

        Returns
        -------
        None

        '''
        cursor = self.connection.cursor()
        try:
            sql = '''delete FROM {}'''.format(self._sanitize(table_name))
            cursor.execute(sql)
            self.connection.commit()
        except Exception as e:
            if "doesn't exist" in str(e):
                print(" Table doesnt exist.")
            else:
                raise e

        if delete_table:
            try:
                sql = '''drop TABLE {}'''.format(self._sanitize(table_name))
                cursor.execute(sql)
                self.connection.commit()
            except Exception as e:
                if "Unknown table" in str(e):
                    print(" Table doesnt exist.")
                else:
                    raise e
        cursor.close()


    def get_sql_column_names(self, table_name:str) -> list[str]:
        '''
        Return the column names from an SQL table.

        Parameters
        ----------
        table_name : str

        Returns
        -------
        list[str]

        '''

        cursor = self.connection.cursor()

        sql = ''' describe  {}.{}'''.format(self._sanitize(self.database),
                                            self._sanitize(table_name))
        cursor.execute(sql)
        col = cursor.fetchall()
        cursor.close()

        #respond with only the column names
        names = [ x[0] for x in col  ]
        return names


    def get_sql_data(self, table_name:str) -> list:
        '''
        Return a list of all data from the SQL table.

        Parameters
        ----------
        table_name : str

        Returns
        -------
        list

        '''
        cursor = self.connection.cursor()
        sql = '''select * from {}'''.format(self._sanitize(table_name))
        cursor.execute(sql)
        table_data = cursor.fetchall()
        cursor.close()

        return table_data

#-------------------------------------------------------------------------

def get_dataframe_results(config:dict, table:str) -> pandas.DataFrame:
    '''
    Using the 'mysql_db_endpoint' and 'database_name' in the config
    dictionary, obtain all data from the 'table' and return in
    a pandas DataFrame

    Parameters
    ----------
    config : dict
        Dictionary containing:
            'mysql_db_endpoint' : location of the sql database
            'database_name' : name of the database to obtain the data
    table : str
        Name of the table to obtain the data from.

    Returns
    -------
    pandas.DataFrame
        SQL data converted into a pandas dataframe

    '''
    secret = get_secret(config['secret_name'], config['region_name'])
    with SQLHandler(secret, config['mysql_db_endpoint'], config['database_name']) as sql:
        table_data = sql.get_sql_data(table)
        cols = sql.get_sql_column_names(table)

    if len(table_data)==0:
        print("WARNING: no data found in table.")
        return pandas.DataFrame()
    df= pandas.DataFrame(table_data)
    df.columns = cols
    return df