from __future__ import annotations
from typing import Any, Generator

import re
from urllib.parse import quote_plus

import psycopg
from psycopg.errors import Error, OperationalError, DuplicateTable, UniqueViolation
from psycopg.sql import SQL, Literal, Placeholder, Identifier, Composed
from psycopg.types.json import Jsonb

from app.utils.db.Table import Table, REX_VALID_NAMES
from app.utils.db.Condition import Condition, EqualCondition, NotEqualCondition, AndCondition, OrCondition, TrueCondition
from app.utils import errors as err
from app.utils.exceptions import RequestException, BugException
from app.utils.logger.logger import logger, logger_sql
from .ClientSQL import ClientSQL



def str_to_varchar(max_len: int = 0) -> str:
    """
    Convert a string type to a varchar()
    """
    if max_len <= 0:
        return "varchar"
    return f"varchar({max_len})"

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
    "dict": "jsonb",
    "json": "jsonb",
    "str": str_to_varchar,
    "list": list_to_array,
    "serial": "serial",
    "int8": "smallint"
}

data_type_postgre_to_sogo : dict[str, Any]= {
    "jsonb": "dict",
    "integer": "int",
    "character varying": "str",
    "ARRAY": "list",
    "smallint": "int8"
}

def table_to_query(table: Table) -> Composed:
    """
    Return the SQL query to create a table
    """
    if not isinstance(table, Table):
        logger_sql.error("Try generate a table without the class Table")
        raise BugException(f": {__name__} Try generate a table without the class Table")

    sql_all_column = []
    for column in table.columns:
        #Get postgre data type
        data_type = data_type_sogo_to_postgre[column.data_type]
        if isinstance(data_type, str):
            pass
        elif callable(data_type):
            if column.extra_args is None:
                data_type = data_type()
            else:
                data_type = data_type(**column.extra_args)

        sql_column = SQL("{column_name} {column_type} ").format(
            column_name=Identifier(column.name),
            column_type=SQL(data_type),
        )

        if not column.is_nullable:
            sql_column = Composed([sql_column, SQL("NOT NULL")])

        if column.is_unique:
            sql_column = Composed([sql_column, SQL(" UNIQUE")])

        sql_all_column.append(sql_column)

    if table.primary_keys:
        sql_all_column.append(SQL("PRIMARY KEY ({})").format(SQL(", ").join(map(Identifier, table.primary_keys))))

    sql_query = SQL("CREATE TABLE {table_name} ({columns})").format(
        table_name=Identifier(table.name),
        columns=SQL(", ").join(sql_all_column)
    )

    return sql_query

def condition_to_query(condition: Condition, add_where : bool = False) -> Composed:
    """
    Return the WHERE part of the sql_query
    """

    if isinstance(condition, EqualCondition):
        sql_condition = SQL("{param} = {value}").format(param=Identifier(condition.param_name), value=Literal(condition.param_value))
    elif isinstance(condition, NotEqualCondition):
        sql_condition = SQL("{param} != {value}").format(param=Identifier(condition.param_name), value=Literal(condition.param_value))
    elif isinstance(condition, AndCondition):
        condition1 = condition_to_query(condition.condition1)
        condition2 = condition_to_query(condition.condition2)
        sql_condition = SQL("({cond1} AND {cond2})").format(cond1=condition1, cond2=condition2)
    elif isinstance(condition, OrCondition):
        condition1 = condition_to_query(condition.condition1)
        condition2 = condition_to_query(condition.condition2)
        sql_condition = SQL("({cond1} OR {cond2})").format(cond1=condition1, cond2=condition2)
    elif isinstance(condition, TrueCondition):
        sql_condition = Composed([SQL("1 = 1")])
    else:
        raise BugException("Trying to convert a Condition not implemented")

    if add_where:
        sql_condition = SQL("WHERE {condition}").format(condition=sql_condition)

    return sql_condition


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
        #TODO: put in redis the number of failed connection, after a threshold, do not attempt and raise a Aggravated exception
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
            raise BugException(f"Trying to get a table info from an invalid table name: {table_name}")

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

    def create_table(self, table : Table) -> None:
        """
        Create a table
        Table should already be sql-exploit free
        """
        if self.db_conn and self.db_conn.closed:
            self.connect()

        sql_query = table_to_query(table)

        logger_sql.info("QUERY: %s", sql_query.as_string())

        if self.db_conn is not None:
            try:
                self.db_conn.execute(sql_query)
            except DuplicateTable:
                logger_sql.warning("Attempted to create a table that already exist %s, the schema may be different", table.name)
            except Error as e:
                logger_sql.error("Error when creating table %s", e)
                self.db_conn.commit()
                raise RequestException("Error when creating table") from e
            finally:
                self.db_conn.commit()

    def create_several_table(self, table_list : list[Table]) -> None:
        """
        Create several tables
        """
        if self.db_conn and self.db_conn.closed:
            self.connect()

        for table in table_list:
            self.create_table(table)

    def insert_in_table(self, table_name: str, column_tuple: tuple[str, ...], values_tuple: list[list[Any]]) -> int:
        """
        Insert one or more row into a table

        raise BugException is a unique value contraint is trigger
        """
        ret = 0
        if self.db_conn and self.db_conn.closed:
            self.connect()

        #Check column len and values len
        insert_len = len(column_tuple)
        sql_all_placeholder = []
        sql_all_values = []
        for values in values_tuple:
            if (value_len := len(values)) != insert_len:
                logger_sql.error("Try to insert more or less data than the columns. Column size: %s, data_size: %s", insert_len, value_len)
                raise BugException(f"Try to insert more or less data than the columns. Column size: {insert_len}, data_size: {value_len}")
            sql_all_placeholder.append(SQL("({})").format(SQL(', ').join(Placeholder() * insert_len)))
            for idx, value in enumerate(values):
                if isinstance(value, dict):
                    values[idx] = Jsonb(value)

            sql_all_values.extend(values)

        sql_query = SQL("INSERT INTO {table_name} ({columns}) VALUES {values}").format(
            table_name=Identifier(table_name),
            columns=SQL(", ").join(map(Identifier, column_tuple)),
            values=SQL(", ").join(sql_all_placeholder)
        )
        logger_sql.info("QUERY COMMAND: %s", sql_query.as_string())

        if self.db_conn is not None:
            try:
                all_record = self.db_conn.execute(sql_query, sql_all_values)
                if all_record.rowcount == 0:
                    logger_sql.info("QUERY RESULT: None inserted")
                else:
                    logger_sql.info("QUERY RESULT: inserted %s rows", all_record.rowcount)
                ret = all_record.rowcount
            except UniqueViolation as e:
                logger_sql.error("Error (%s) when inserting table %s", type(e), e)
                raise BugException("Unique Violation in database") from e
            except Error as e:
                logger_sql.error("Error (%s) when inserting table %s", type(e), e)
            finally:
                self.db_conn.commit()

        return ret

    def update_in_table(self, table_name: str, column_tuple: tuple, values_list: list, condition: Condition) -> int:
        """
        Update data in a table
        """
        ret = 0
        if self.db_conn and self.db_conn.closed:
            self.connect()

        #Check column len and values len
        insert_len = len(column_tuple)
        if (value_len := len(values_list)) != insert_len:
            logger_sql.error("Try to update more or less data than the specified columns. Column size: %s, data_size: %s", insert_len, value_len)
            raise BugException(f"Try to update more or less data than the specified columns. Column size: {insert_len}, data_size: {value_len}")

        #Prepare placeholders and convert dict to Jsonb
        sql_all_placeholder = [SQL("({})").format(SQL(', ').join(Placeholder() * insert_len))]
        for idx, value in enumerate(values_list):
            if isinstance(value, dict):
                values_list[idx] = Jsonb(value)

        #Create and execute the query
        sql_query = SQL("UPDATE {table_name} SET ({columns}) = ROW{values} {conditions}").format(
            table_name=Identifier(table_name),
            columns=SQL(", ").join(map(Identifier, column_tuple)),
            values=SQL(", ").join(sql_all_placeholder),
            conditions=condition_to_query(condition, add_where=True)
        )

        if self.db_conn is not None:
            logger_sql.info("QUERY COMMAND: '%s' with values: '%s'", sql_query.as_string(), values_list)
            try:
                all_record = self.db_conn.execute(sql_query, values_list)
                if all_record.rowcount == 0:
                    logger_sql.info("QUERY RESULT: None updated")
                else:
                    logger_sql.info("QUERY RESULT: updated %s rows", all_record.rowcount)
                ret = all_record.rowcount
            except Error as e:
                logger_sql.error("Error (%s) when updating table %s", type(e), e)
            finally:
                self.db_conn.commit()

        return ret

    def select_from_table(self, table_name: str, column_tuple: tuple[str, ...], condition: Condition, offset: int = 0, limit: int = 0) -> Generator[tuple[Any, ...]]:
        """
        Select values from a table under conditions

        offset = 0 means not offset
        limit = 0 means not limit (LIMIT ALL)

        :param table_name: Name fo the table
        :type table_name: str
        :param column_tuple: Tuple of the column name to select
        :type column_tuple: tuple[str]
        :param condition: Condition on the query
        :type condition: Condition
        :yield: A generator, each item is a tuple with the values corresponding to the column_tuple param
        :rtype: Generator[tuple[Any, ...]]
        """
        if self.db_conn and self.db_conn.closed:
            self.connect()
        if len(column_tuple) == 0:
            column_tuple = ("*",)
        if limit == 0:
            limit_query = Composed([SQL("ALL")])
        else:
            limit_query = Composed([Literal(limit)])

        sql_query = SQL("SELECT {columns} FROM {table_name} {conditions} LIMIT {limit} OFFSET {offset}").format(
            columns=SQL(", ").join(map(SQL, column_tuple)),
            table_name=Identifier(table_name),
            conditions=condition_to_query(condition, add_where=True),
            limit = limit_query,
            offset = Literal(offset)
        )

        logger_sql.info("QUERY COMMAND 2: %s",sql_query.as_string())

        if self.db_conn is not None:
            try:
                all_record = self.db_conn.execute(sql_query)
                if all_record.rowcount == 0:
                    logger_sql.info("QUERY RESULT: empty")
                else:
                    logger_sql.info("QUERY RESULT: fetch %s rows", all_record.rowcount)
                while record := all_record.fetchone():
                    yield record
            except Error as e:
                logger_sql.error("Error when selecting table %s", e)
            finally:
                self.db_conn.commit()

    def select_from_several_table(self, table_name: str, column_tuple: tuple, condition: Condition) -> Generator[tuple[Any, ...]]:
        """
        select values from several tables
        """
        logger_sql.error("Method 'select_from_several_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    def count_row_in_table(self, table_name: str, condition: Condition, column_name: str = "*") -> int:
        """
        Select values from a table under conditions

        :param table_name: Name fo the table
        :type table_name: str
        :param colum_name: Name of the column, or "*" by default
        :type colum_name: str
        :param condition: Condition on the query
        :type condition: Condition
        :return: A number indicates the number of row of the result
        :rtype: int
        """
        if self.db_conn and self.db_conn.closed:
            self.connect()
        if column_name == "*":
            count_query = Composed([SQL("COUNT(*)")])
        else:
            count_query = SQL("COUNT({column})").format(column=Identifier(column_name))
        sql_query = SQL("SELECT {count} FROM {table_name} {conditions}").format(
            count=count_query,
            table_name=Identifier(table_name),
            conditions=condition_to_query(condition, add_where=True)
        )

        logger_sql.info("QUERY COMMAND: %s",sql_query.as_string())

        count_ret = 0
        if self.db_conn is not None:
            try:
                all_records = self.db_conn.execute(sql_query)
                while record:= all_records.fetchone():
                    count_ret = record[0]
                logger_sql.info("QUERY RESULT: COUNT: %s rows", count_ret)
            except Error as e:
                logger_sql.error("Error when selecting table %s", e)
            finally:
                self.db_conn.commit()
        return count_ret

    def delete_row_in_table(self, table_name: str, condition: Condition, expected_row: int = 0) -> int:
        """
        Delete rows in a table.

        Conditon cannot be of type TrueCondition

        Set expected_row to a value greater than 0 to check beforehand with a COUNT if your condition
        returns the expecte number of rows. 0 or negative values will not trigger any check.

        Example:
        If you're sure that only one row will be deleted, set expected_row=1 and this method
        will check before the delete query if, indeed, only 1 row will be deleted.

        :param table_name: Name of the table
        :type table_name: str
        :param condition: Condition for the query
        :type condition: Condition
        :param expected_row: Expected number of rows to be deleted, defaults to 0
        :type expected_row: int, optional
        :raises BugRequest: raise if the condition is of type TrueCondition
        :raises RequestException: raise if the expected number of rows doesn't match
        :return: number of rows deleted
        :rtype: int
        """
        if isinstance(condition, TrueCondition):
            raise BugException("Condition for delete query is always True", err.ERROR_QUERY_DELETION_CONDITION)

        if self.db_conn and self.db_conn.closed:
            self.connect()
        
        if expected_row > 0:
            #First count the row to be deleted and check if it matches
            row_affected = self.count_row_in_table(table_name, condition)
            if expected_row != row_affected:
                raise RequestException(f"Expected number or row deleted is different! expected: {expected_row}, real {row_affected}", err.ERROR_QUERY_DELETION_ROWS)

        sql_query = SQL("DELETE FROM {table_name} {conditions}").format(
            table_name=Identifier(table_name),
            conditions=condition_to_query(condition, add_where=True)
        )

        logger_sql.info("QUERY COMMAND: %s",sql_query.as_string())

        count_ret = 0
        if self.db_conn is not None:
            try:
                all_records = self.db_conn.execute(sql_query)
                count_ret = all_records.rowcount
                if count_ret == 0:
                    logger_sql.info("QUERY RESULT: None deleted")
                else:
                    logger_sql.info("QUERY RESULT: deleted %s rows", count_ret)
            except Error as e:
                logger_sql.error("Error when selecting table %s", e)
            finally:
                self.db_conn.commit()
        return count_ret

    def close(self) -> None:
        """
        Close the connection to the database 
        """
        if self.db_conn is not None and not self.db_conn.closed:
            self.db_conn.close()
