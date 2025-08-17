from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

import re
from urllib.parse import quote_plus

import psycopg
from psycopg.errors import Error, OperationalError, DuplicateTable
from psycopg.sql import SQL, Literal, Placeholder, Identifier

from app.utils.logger.logger import logger, logger_sql
from app.utils.exceptions import RequestException
from .ClientSQL import ClientSQL
from .Table import Table, REX_VALID_NAMES


def str_to_varchar(max_len: int = 0) -> str:
    """
    Convert a string type to a varchar()
    """
    if max_len == 0:
        return "VARCHAR()"
    return f"VARCHAR({max_len})"

def list_to_array(data_type: str, extra_args: dict = None) -> str:
    """
    Convert a list type to an ARRAY
    """
    data_type = data_type_sogo_to_postgre[data_type]
    if isinstance(data_type, str):
        pass
    elif callable(data_type):
        if extra_args is None:
            data_type = data_type()
        else:
            data_type = data_type(**extra_args)

    return f"{data_type}[]"


data_type_sogo_to_postgre : dict[str, Any]= {
    "dict": "JSONB",
    "json": "JSONB",
    "str": str_to_varchar,
    "list": list_to_array,
    "serial": "SERIAL"
}

data_type_postgre_to_sogo : dict[str, Any]= {
    "jsonb": "dict",
    "integer": "int",
    "character varying": "str",
    "ARRAY": "list"
}


class ClientPostgreSQL(ClientSQL):
    """
    Class to connect, read and write into a sql database
    """

    def __init__(self, db_user: str, db_pwd: str, db_host: str, db_port: int,  db_ssl: bool, db_enc: str):
        """
        Init the PostgreSQL client.
        It shouldn't raise any Exception as SOGo will instantiate the object but not necessarily use it right on spot
        """
        self.conn_string: str      = f"postgresql://{quote_plus(db_user)}:{quote_plus(db_pwd)}@{db_host}:{db_port}/sogo?client_encoding={db_enc}"
        self.safe_conn_string: str = f"postgresql://SOGO_P_DB_USER:SOGO_P_DB_PWD@{db_host}:{db_port}/sogo?client_encoding={db_enc}"
        self.db_conn: psycopg.Connection | None = None

    def connect(self) -> None:
        """
        Connect to the database and check if this is ok
        """
        try:
            self.db_conn = psycopg.connect(self.conn_string, connect_timeout=5)
        except (OperationalError, Error) as e:
            logger.error("Cannot connect to %s reason: %s", self.safe_conn_string, repr(e))
            raise RequestException("Postgresql database connection error") from e


    def get_table_info(self, table_name: str) -> dict | None:
        """
        Return None if the table was not found
        If found, return a dict as {"column_name": "data_type", ...}
        """

        if not re.match(REX_VALID_NAMES, table_name):
            logger_sql.error("Trying to get a table info from an invalid table name: %s", table_name)

        if self.db_conn is None or self.db_conn.closed:
            self.connect()

        ret = {}
        sql_query = SQL("SELECT column_name, data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = {}").format(Literal(table_name))

        all_record : list = []

        logger_sql.info("QUERY COMMAND: %s", sql_query.as_string())

        if self.db_conn is not None:
            try:
                all_record = self.db_conn.execute(sql_query).fetchall()
                logger_sql.info("QUERY RESULT: %s", all_record)
            except Error as e:
                logger_sql.error("Error when fetching table info: %s", e)
            finally:
                self.db_conn.commit()

            for col_name, data_type in all_record:
                ret[col_name] = data_type_postgre_to_sogo[data_type]

        return ret

    def _table_to_query(self, table: Table) -> str:
        """
        Return the SQL query to create a table
        """
        if not isinstance(table, Table):
            logger.error("Try generate a table without the class Table")
        sql_query = f"CREATE TABLE {table.name} ("
        for column in table.columns:
            #Get postgre data type
            data_type = data_type_sogo_to_postgre[column.data_type]
            if isinstance(data_type, str):
                pass
            elif callable(data_type):
                data_type = data_type(**column.extra_args)

            sql_query += f"{column.name} {data_type}"
            if not column.is_nullable:
                sql_query += " NOT NULL"
            sql_query += ","
        if table.primary_key:
            sql_query += f" PRIMARY KEY ({table.primary_key})"
        sql_query += ")"

        return sql_query

    def create_table(self, table : Table) -> None:
        """
        Create a table
        Table should already be sql-exploit free
        """
        if not isinstance(table, Table):
            logger.error("Try generate a table without the class Table")
            return

        if self.db_conn and self.db_conn.closed:
            self.connect()

        sql_query = self._table_to_query(table)

        logger_sql.info("QUERY: %s", sql_query)

        if self.db_conn is not None:
            try:
                self.db_conn.execute(sql_query)
            except DuplicateTable:
                logger_sql.warning("Attempted to create a table that already exist %s, the schema may be different", table.name)
            except Error as e:
                logger_sql.error("Error when creating table %s", e)
            finally:
                self.db_conn.commit()

    def create_several_table(self, table_list : list[Table]) -> None:
        """
        Create several tables
        """
        if not isinstance(table_list, list):
            logger.error("Try generate several table without a list")
            return

        if self.db_conn and self.db_conn.closed:
            self.connect()

        for table in table_list:
            self.create_table(table)

    def insert_in_table(self, table_name: str, column_tuple: tuple, values_tuple: list[tuple]) -> None:
        """
        Insert one or more row into a table
        """
        sql_query = f"INSERT INTO {table_name} {column_tuple} VALUES "
        for idx, value in enumerate(values_tuple):
            if idx == len(values_tuple) - 1:
                sql_query += f"{value}"
            else:
                sql_query += f"{value}, "
        
        logger_sql.info("QUERY: %s", sql_query)
        

    def close(self) -> None:
        """
        Close the connection to the database
        """
        if self.db_conn is not None and not self.db_conn.closed:
            self.db_conn.close()
