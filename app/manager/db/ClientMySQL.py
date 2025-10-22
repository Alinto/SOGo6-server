from __future__ import annotations
from typing import Any, Optional, Generator, Tuple, List, cast

import re
import json
from urllib.parse import quote_plus

import mysql.connector
from mysql.connector import Error, ProgrammingError  # pylint: disable=no-name-in-module

from app.utils.db.Table import Table, REX_VALID_NAMES
from app.utils.db.Condition import Condition, EqualCondition, NotEqualCondition, AndCondition, OrCondition
from app.utils.exceptions import RequestException, BugException
from app.utils.logger.logger import logger, logger_sql
from .ClientSQL import ClientSQL


def str_to_varchar(max_len: int = 0) -> str:
    """
    Convert a string type to a VARCHAR()
    """
    if max_len <= 0:
        return "VARCHAR(255)"
    return f"VARCHAR({max_len})"


def list_to_json(data_type: str | None = None, extra_args: dict | None = None) -> str:
    """
    MySQL does not have a native array type similar to PostgreSQL arrays.
    We'll store lists as JSON.

    Signature intentionally accepts (data_type, extra_args) to mirror PostgreSQL
    list_to_array signature so table_to_query can call with kwargs like {"data_type": "str"}.
    """
    return "JSON"


data_type_sogo_to_mysql: dict[str, Any] = {
    "dict": "JSON",
    "json": "JSON",
    "str": str_to_varchar,
    "list": list_to_json,
    "serial": "BIGINT AUTO_INCREMENT",
    "int8": "SMALLINT",
}

data_type_mysql_to_sogo: dict[str, str] = {
    "json": "dict",
    "varchar": "str",
    "char": "str",
    "text": "str",
    "int": "int",
    "integer": "int",
    "bigint": "int",
    "smallint": "int8",
    "tinyint": "int",
}


def table_to_query(table: Table) -> str:
    """
    Return the SQL string to create a table in MySQL
    """
    if not isinstance(table, Table):
        logger_sql.error("Try generate a table without the class Table")
        raise BugException(f": {__name__} Try generate a table without the class Table")

    sql_all_column: List[str] = []
    for column in table.columns:
        # Get mysql data type
        data_type = data_type_sogo_to_mysql[column.data_type]
        if isinstance(data_type, str):
            column_type = data_type
        elif callable(data_type):
            if column.extra_args is None:
                column_type = data_type()
            else:
                column_type = data_type(**column.extra_args)
        else:
            raise BugException("Invalid data type mapping for mysql")

        sql_column = f"`{column.name}` {column_type}"

        if not column.is_nullable:
            sql_column += " NOT NULL"
        else:
            # for testing clarity
            sql_column += " "

        if column.is_unique:
            sql_column += " UNIQUE"

        sql_all_column.append(sql_column)

    if table.primary_keys:
        pk = ", ".join(f"`{p}`" for p in table.primary_keys)
        sql_all_column.append(f"PRIMARY KEY ({pk})")

    sql_query = f"CREATE TABLE `{table.name}` ({', '.join(sql_all_column)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    return sql_query


def condition_to_query(condition: Condition, add_where: bool = False) -> Tuple[str, List[Any]]:
    """
    Convert Condition objects into a SQL WHERE fragment and a list of parameter values.

    Returns: (sql_fragment, params)
    Example: ("WHERE (`col1` = %s AND `col2` != %s)", [val1, val2])
    """
    params: List[Any] = []

    if isinstance(condition, EqualCondition):
        sql_condition = f"`{condition.param_name}` = %s"
        params.append(condition.param_value)
    elif isinstance(condition, NotEqualCondition):
        sql_condition = f"`{condition.param_name}` != %s"
        params.append(condition.param_value)
    elif isinstance(condition, AndCondition):
        cond1_sql, cond1_params = condition_to_query(condition.condition1)
        cond2_sql, cond2_params = condition_to_query(condition.condition2)
        if cond1_sql.strip().upper().startswith("WHERE "):
            cond1_sql = cond1_sql.strip()[6:]
        if cond2_sql.strip().upper().startswith("WHERE "):
            cond2_sql = cond2_sql.strip()[6:]
        sql_condition = f"({cond1_sql} AND {cond2_sql})"
        params.extend(cond1_params)
        params.extend(cond2_params)
    elif isinstance(condition, OrCondition):
        cond1_sql, cond1_params = condition_to_query(condition.condition1)
        cond2_sql, cond2_params = condition_to_query(condition.condition2)
        if cond1_sql.strip().upper().startswith("WHERE "):
            cond1_sql = cond1_sql.strip()[6:]
        if cond2_sql.strip().upper().startswith("WHERE "):
            cond2_sql = cond2_sql.strip()[6:]
        sql_condition = f"({cond1_sql} OR {cond2_sql})"
        params.extend(cond1_params)
        params.extend(cond2_params)
    else:
        logger_sql.error("Unknown Condition type %s", type(condition))
        raise BugException("Unknown Condition type")

    if add_where:
        sql_condition = "WHERE " + sql_condition

    return sql_condition, params


class ClientMySQL(ClientSQL):
    """
    MySQL implementation of ClientSQL
    """

    def __init__(self, db_user: str, db_pwd: str, db_host: str, db_port: int, db_ssl: bool, db_enc: str):
        """
        Init the MySQL client.
        """
        self.safe_conn_string: str = f"mysql://SOGO_M_DB_USER:SOGO_M_DB_PWD@{db_host}:{db_port}/sogo?charset={db_enc}"
        self.conn_config = {
            "user": db_user,
            "password": db_pwd,
            "host": db_host,
            "port": db_port,
            "database": "sogo",
            "connection_timeout": 5,
            "use_pure": True,
            "charset": db_enc,
        }
        self.db_conn: Any = None

    def connect(self) -> None:
        """
        Connect to the MySQL database and check if this is OK.
        """
        try:
            self.db_conn = mysql.connector.connect(**self.conn_config)
        except Error as e:
            logger.error("Cannot connect to %s reason: %s", self.safe_conn_string, repr(e))
            raise RequestException("MySQL database connection error") from e

    def get_table_info(self, table_name: str) -> dict | None:
        """
        Return None if the table was not found.
        If found, return a dict as {"column_name": "data_type", ...}
        """
        if not re.match(REX_VALID_NAMES, table_name):
            logger_sql.error("Trying to get a table info from an invalid table name: %s", table_name)
            raise BugException(f"Trying to get a table info from an invalid table name: {table_name}")

        if self.db_conn is None or not self.db_conn.is_connected():
            self.connect()

        ret: dict = {}
        sql_query = "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s"

        params = cast(Tuple[str, str], (str(self.conn_config["database"]), str(table_name)))

        logger_sql.info("QUERY COMMAND: %s -- params=%s", sql_query, params)

        if self.db_conn is not None:
            cursor = self.db_conn.cursor()
            try:
                cursor.execute(sql_query, params)
                all_record = cursor.fetchall()
                logger_sql.info("QUERY RESULT: %s", all_record)
            except Error as e:
                logger_sql.error("Error when fetching table info: %s", e)
                all_record = []
            finally:
                cursor.close()

            for col_name, data_type in all_record:
                data_type_lower = str(data_type).lower()
                ret[col_name] = data_type_mysql_to_sogo.get(data_type_lower, "str")

        return ret

    def create_table(self, table: Table) -> None:
        """
        Create a table in MySQL. Table should already be sql-exploit free (names validated).
        """
        if self.db_conn and not self.db_conn.is_connected():
            self.connect()

        sql_query = table_to_query(table)
        logger_sql.info("QUERY: %s", sql_query)

        if self.db_conn is not None:
            cursor = self.db_conn.cursor()
            try:
                cursor.execute(sql_query)
                self.db_conn.commit()
            except ProgrammingError as e:
                if "already exists" in str(e).lower():
                    logger_sql.warning("Attempted to create a table that already exist %s, the schema may be different", table.name)
                else:
                    logger_sql.error("Error when creating table %s: %s", table.name, e)
                    self.db_conn.rollback()
                    raise RequestException("Error when creating table") from e
            except Error as e:
                logger_sql.error("Error when creating table %s: %s", table.name, e)
                self.db_conn.rollback()
                raise RequestException("Error when creating table") from e
            finally:
                cursor.close()

    def create_several_table(self, table_list: list[Table]) -> None:
        """
        Create several tables
        """
        if self.db_conn and not self.db_conn.is_connected():
            self.connect()

        for table in table_list:
            self.create_table(table)

    def insert_in_table(self, table_name: str, column_tuple: tuple[str, ...], values_tuple: list[list[Any]]) -> int:
        """
        Insert one or more rows into a table
        """
        ret = 0
        if self.db_conn and not self.db_conn.is_connected():
            self.connect()

        insert_len = len(column_tuple)
        sql_all_values: List[Any] = []
        placeholders_per_row = "(" + ", ".join(["%s"] * insert_len) + ")"
        sql_all_placeholder = []

        for values in values_tuple:
            if (value_len := len(values)) != insert_len:
                logger_sql.error("Try to insert more or less data than the columns. Column size: %s, data_size: %s", insert_len, value_len)
                raise BugException(f"Try to insert more or less data than the columns. Column size: {insert_len}, data_size: {value_len}")
            for idx, value in enumerate(values):
                if isinstance(value, dict) or isinstance(value, list):
                    values[idx] = json.dumps(value)
            sql_all_placeholder.append(placeholders_per_row)
            sql_all_values.extend(values)

        columns_sql = ", ".join(f"`{c}`" for c in column_tuple)
        sql_query = f"INSERT INTO `{table_name}` ({columns_sql}) VALUES {', '.join(sql_all_placeholder)}"

        logger_sql.info("QUERY COMMAND: %s -- params=%s", sql_query, sql_all_values)

        if self.db_conn is not None:
            cursor = self.db_conn.cursor()
            try:
                cursor.execute(sql_query, tuple(sql_all_values))
                ret = cursor.rowcount or 0
                if ret == 0:
                    logger_sql.info("QUERY RESULT: None inserted")
                else:
                    logger_sql.info("QUERY RESULT: inserted %s rows", ret)
                self.db_conn.commit()
            except Error as e:
                logger_sql.error("Error (%s) when inserting table %s: %s", type(e), table_name, e)
                self.db_conn.rollback()
            finally:
                cursor.close()

        return ret

    def update_in_table(self, table_name: str, column_tuple: tuple, values_list: list, condition: Condition) -> int:
        """
        Update rows in a table
        """
        ret = 0
        if self.db_conn and not self.db_conn.is_connected():
            self.connect()

        # Check column len and values len
        insert_len = len(column_tuple)
        if (value_len := len(values_list)) != insert_len:
            logger_sql.error("Try to update more or less data than the specified columns. Column size: %s, data_size: %s", insert_len, value_len)
            raise BugException(f"Try to update more or less data than the specified columns. Column size: {insert_len}, data_size: {value_len}")

        # Prepare set expressions and convert dict/list to json strings
        set_parts = []
        params: List[Any] = []
        for idx, col in enumerate(column_tuple):
            val = values_list[idx]
            if isinstance(val, dict) or isinstance(val, list):
                val = json.dumps(val)
            set_parts.append(f"`{col}` = %s")
            params.append(val)

        cond_sql, cond_params = condition_to_query(condition, add_where=True)
        params.extend(cond_params)

        # Create and execute the query
        sql_query = f"UPDATE `{table_name}` SET {', '.join(set_parts)} {cond_sql}"

        if self.db_conn is not None:
            logger_sql.info("QUERY COMMAND: %s -- params=%s", sql_query, params)
            cursor = self.db_conn.cursor()
            try:
                cursor.execute(sql_query, tuple(params))
                ret = cursor.rowcount or 0
                if ret == 0:
                    logger_sql.info("QUERY RESULT: None updated")
                else:
                    logger_sql.info("QUERY RESULT: updated %s rows", ret)
                self.db_conn.commit()
            except Error as e:
                logger_sql.error("Error (%s) when updating table %s: %s", type(e), table_name, e)
                self.db_conn.rollback()
            finally:
                cursor.close()

        return ret

    def select_from_table(self, table_name: str, column_tuple: tuple[str], condition: Condition) -> Generator[tuple[Any, ...], None, None]:
        """
        Select values from a table under conditions
        """
        if self.db_conn and not self.db_conn.is_connected():
            self.connect()
        if len(column_tuple) == 0:
            columns_sql = "*"
        else:
            if len(column_tuple) == 1 and column_tuple[0] == "*":
                columns_sql = "*"
            else:
                columns_sql = ", ".join(f"`{c}`" for c in column_tuple)

        cond_sql, params = condition_to_query(condition, add_where=True)
        sql_query = f"SELECT {columns_sql} FROM `{table_name}` {cond_sql}"

        logger_sql.info("QUERY COMMAND: %s -- params=%s", sql_query, params)

        if self.db_conn is not None:
            cursor = self.db_conn.cursor()
            try:
                cursor.execute(sql_query, tuple(params))
                rows_fetched = cursor.rowcount
                if rows_fetched == 0:
                    logger_sql.info("QUERY RESULT: empty")
                else:
                    logger_sql.info("QUERY RESULT: fetch %s rows", rows_fetched)
                while True:
                    record = cursor.fetchone()
                    if record is None:
                        break
                    yield record
            except Error as e:
                logger_sql.error("Error when selecting table %s: %s", table_name, e)
            finally:
                cursor.close()

    def select_from_several_table(self, table_name: str, column_tuple: tuple, condition: Condition) -> Generator[tuple[Any, ...], None, None]:
        """
        select values from several tables - not implemented for MySQL client
        """
        logger_sql.error("Method 'select_from_several_table' of ClientMySQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    def close(self) -> None:
        """
        Close the connection to the database 
        """
        if self.db_conn is not None and self.db_conn.is_connected():
            try:
                self.db_conn.close()
            except Error as e:
                logger_sql.error("Error while closing mysql connection: %s", e)
