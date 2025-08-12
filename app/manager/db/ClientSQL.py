from app.utils.logger.logger import logger, logger_sql

from .Table import Table

class ClientSQL:
    """
    Abstratc class inherited by differents kind of sql client
    """
    def __init__(self):
        """
        It shouldn't raise any Exception as SOGo will instantiate the object but not necessarily use it right on spot
        """
        pass

    def connect(self):
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

    def close(self):
        """
        Close the connection to the database
        """
        logger_sql.error("Method 'connect' of clientSQL must be defined inside children %s", type(self).__name__)