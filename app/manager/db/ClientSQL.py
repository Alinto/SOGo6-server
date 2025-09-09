from typing import TYPE_CHECKING, Any, Generator
from abc import abstractmethod, ABCMeta
from app.utils.logger.logger import logger, logger_sql

from app.utils.db.Table import Table
from app.utils.db.Condition import Condition

class ClientSQL(metaclass=ABCMeta):
    """
    Abstract class inherited by differents kind of sql client
    """
    def __init__(self) -> None:
        """
        It shouldn't raise any Exception as SOGo will instantiate the object but not necessarily use it right on spot
        """

    @abstractmethod
    def connect(self) -> None:
        """
        Connect to the database and check this is ok
        """
        logger_sql.error("Method 'connect' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def get_table_info(self, table_name: str) -> dict[str,str] | None:
        """
        Return None if the table was not found
        If found return a dict as {"column_name": "data_type", ...}
        """
        logger_sql.error("Method 'get_table_info' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def create_table(self, table: Table) -> None:
        """
        Create a table
        """
        logger_sql.error("Method 'create_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def create_several_table(self, table_list : list[Table]) -> None:
        """
        Create several tables
        """
        logger_sql.error("Method 'create_several_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def select_from_table(self, table_name: str, column_tuple: tuple, condition: Condition) -> Generator[tuple[Any, ...]]:
        """
        select values from a table
        """
        logger_sql.error("Method 'select_from_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def select_from_several_table(self, table_name: str, column_tuple: tuple, condition: Condition) -> Generator[tuple[Any, ...]]:
        """
        select values from several tables
        """
        logger_sql.error("Method 'select_from_several_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def insert_in_table(self, table_name: str, column_tuple: tuple[str, ...], values_tuple: list[list[Any]]) -> int:
        """
        Insert one or more row into a table
        """
        logger_sql.error("Method 'insert_in_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def update_in_table(self, table_name: str, column_tuple: tuple, values_list: list, condition: Condition) -> int:
        """
        Update rows in a table
        """
        logger_sql.error("Method 'update_in_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """
        Close the connection to the database
        """
        logger_sql.error("Method 'close' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError
