from typing import TYPE_CHECKING, Any, Optional, Generator

from app.utils.logger.logger import logger, logger_sql

from app.utils.db.Table import Table
from app.utils.db.Condition import Condition

class ClientSQL:
    """
    Abstratc class inherited by differents kind of sql client
    """
    def __init__(self) -> None:
        """
        It shouldn't raise any Exception as SOGo will instantiate the object but not necessarily use it right on spot
        """

    def connect(self) -> None:
        """
        Connect to the database and check this is ok
        """
        logger_sql.error("Method 'connect' of clientSQL must be defined inside children %s", type(self).__name__)

    def get_table_info(self, table_name: str) -> dict[str,str] | None:
        """
        Return None if the table was not found
        If found return a dict as {"column_name": "data_type", ...}
        """
        logger_sql.error("Method 'get_table_info' of clientSQL must be defined inside children %s", type(self).__name__)
        return None

    def create_table(self, table: Table) -> None:
        """
        Create a table
        """
        logger_sql.error("Method 'create_table' of clientSQL must be defined inside children %s", type(self).__name__)

    def create_several_table(self, table_list : list[Table]) -> None:
        """
        Create several tables
        """
        logger_sql.error("Method 'create_several_table' of clientSQL must be defined inside children %s", type(self).__name__)

    def select_from_table(self, table_name: str, column_tuple: tuple, condition: Condition) -> Generator[tuple[Any, ...]]:
        """
        Insert one or more row into a table
        """
        logger_sql.error("Method 'insert_in_table' of clientSQL must be defined inside children %s", type(self).__name__)
        yield ()

    def select_from_several_table(self, table_name: str, column_tuple: tuple, condition: Condition) -> None:
        """
        Insert one or more row into a table
        """
        logger_sql.error("Method 'insert_in_table' of clientSQL must be defined inside children %s", type(self).__name__)

    def insert_in_table(self, table_name: str, column_tuple: tuple[str, ...], values_tuple: list[tuple[Any, ...]]) -> int:
        """
        Insert one or more row into a table
        """
        logger_sql.error("Method 'insert_in_table' of clientSQL must be defined inside children %s", type(self).__name__)
        return -1

    def update_in_table(self, table_name: str, column_tuple: tuple, values_tuple: tuple, condition: Condition) -> None:
        """
        Insert data in a table
        """
        logger_sql.error("Method 'insert_in_table' of clientSQL must be defined inside children %s", type(self).__name__)

    def close(self) -> None:
        """
        Close the connection to the database
        """
        logger_sql.error("Method 'connect' of clientSQL must be defined inside children %s", type(self).__name__)