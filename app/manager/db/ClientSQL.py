from typing import Any, Generator
from abc import abstractmethod, ABCMeta

from app.utils.logger.logger import logger
from app.utils.db.Table import Table
from app.utils.db.Condition import Condition, FullTextCondition, JoinClause, Order


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
        Connect to the database and check this is ok.
        /!\\ Beware must match ClientUserSource method as pylint nor mypy catch the error
        """
        logger.error("Method 'connect' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def get_table_info(self, table_name: str) -> dict[str,str] | None:
        """
        Return None if the table was not found
        If found return a dict as {"column_name": "data_type", ...}
        """
        logger.error("Method 'get_table_info' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def create_table(self, table: Table) -> None:
        """
        Create a table
        """
        logger.error("Method 'create_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def create_indexes(self, table: Table) -> None:
        """Create all indexes defined on the table. Skips indexes that already exist."""
        raise NotImplementedError

    @abstractmethod
    def create_several_table(self, table_list : list[Table]) -> None:
        """
        Create several tables
        """
        logger.error("Method 'create_several_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def select_from_table(self, table_name: str, column_tuple: tuple[str, ...], condition: Condition,
                          offset: int = 0, limit: int = 0,
                          sort_by: str | None = None, order: Order = Order.ASC,
                          rank_by: FullTextCondition | None = None) -> Generator[tuple[Any, ...]]:
        """
        select values from a table

        :param table_name: Name of the table
        :type table_name: str
        :param column_tuple: Tuple of the column names to select
        :type column_tuple: tuple[str, ...]
        :param condition: Condition on the query
        :type condition: Condition
        :param offset: Number of rows to skip, defaults to 0
        :type offset: int
        :param limit: Maximum number of rows to return, defaults to 0 (no limit)
        :type limit: int
        :param sort_by: Column name to sort by, defaults to None
        :type sort_by: str | None
        :param order: Sort direction (ASC or DESC), defaults to Order.ASC
        :type order: Order
        :param rank_by: When set, order by full-text relevance of this match (most relevant
            first), with sort_by kept as a secondary tiebreaker. Defaults to None.
        :type rank_by: FullTextCondition | None
        """
        logger.error("Method 'select_from_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def select_from_several_table(
        self,
        table_name: str,
        joins: list[JoinClause],
        column_tuple: tuple[str, ...],
        condition: Condition,
        sort_by: str | None = None,
        order: Order = Order.ASC,
        limit: int = 0,
    ) -> Generator[tuple[Any, ...]]:
        """Select values from several tables using INNER JOIN.

        Column names and condition param_names support qualified names (table.column).

        :param table_name: The base table.
        :param joins: List of JoinClause describing each INNER JOIN.
        :param column_tuple: Columns to select (qualified names recommended).
        :param condition: WHERE condition (use qualified param_names for ambiguous columns).
        :param sort_by: Qualified column name to sort by.
        :param order: Sort direction (ASC or DESC), defaults to Order.ASC.
        :param limit: Maximum rows (0 = no limit).
        """
        logger.error("Method 'select_from_several_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def count_row_in_table(self, table_name: str, condition: Condition, column_name: str = "*") -> int:
        """
        count row in a table
        """
        logger.error("Method 'count_row_in_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError


    @abstractmethod
    def insert_in_table(self, table_name: str, column_tuple: tuple[str, ...], values_tuple: list[list[Any]]) -> int:
        """
        Insert one or more row into a table
        """
        logger.error("Method 'insert_in_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def update_in_table(self, table_name: str, column_tuple: tuple, values_list: list, condition: Condition) -> int:
        """
        Update rows in a table
        """
        logger.error("Method 'update_in_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
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
        logger.error("Method 'delete_row_in_table' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """
        Close the connection to the database
        """
        logger.error("Method 'close' of clientSQL must be implemented by the children %s", type(self).__name__)
        raise NotImplementedError
