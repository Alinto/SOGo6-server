import re

from app.utils.logger.logger import logger

REX_VALID_NAMES = r"^[A-Za-z_0-9]+$" #We force the fact that tables and columns' name must be alphanumerical with underscore only

SOGO_DB_DATA_TYPE = {"dict", "str", "list", "serial", "json", "int8"}
SOGO_DB_DATA_TYPE_VALIDATION = {
    "dict":   {"dict", "json"} ,
    "str":    {"str"},
    "list":   {"list"},
    "serial": {"serial", "int"},
    "json":   {"dict", "json"},
    "int8":   {"number", "smallint", "int8"}
}

class Column:
    """
    Is a common db class. Each db manager will convert this column properly to their own dbapi

    """
    def __init__(self, name: str, data_type: str, is_nullable: bool = False, is_unique: bool = False, extra_args: dict = None):
        """
        An agnostic sogo database column representation. Each database manager must convert this class to their proper syntax

        :param name: Name of the column, must match the regex r"^[A-Za-z_0-9]+$"
        :type name: str
        :param data_type: type of the data, must be one of {"dict", "str", "list", "serial", "json", "int8"}
        :type data_type: str
        :param is_nullable: Can this column be Null, defaults to False
        :type is_nullable: bool, optional
        :param is_unique: Are each value of this column unique. Note that if the column become a primary key, there is no need to set this to True, defaults to False
        :type is_unique: bool, optional
        :param extra_args: Extra arguments for this column, defaults to None
        :type extra_args: dict, optional
        """
        if not isinstance(name, str) or len(name) == 0:
            logger.error("Try to instantiate Column with no name")
        if not re.match(REX_VALID_NAMES, name):
            logger.error("Try to instantiate Column with an unvalid name: %s", name)
        if not data_type in SOGO_DB_DATA_TYPE:
            logger.error("Try to instantiate Column with an invalid type: %s", data_type)

        self.name            = name
        self.data_type       = data_type
        self.data_type_check = SOGO_DB_DATA_TYPE_VALIDATION[data_type]
        self.is_nullable     = is_nullable
        self.is_unique       = is_unique
        self.extra_args      = extra_args

class Index:
    """
    Is a common db class. Each db manager will convert this index properly to their own dbapi
    """
    def __init__(self) -> None:
        pass

class Table:
    """
    Is a common db class. Each db manager will convert this table properly to their own dbapi
    """

    def __init__(self, name: str, columns: list[Column], primary_keys: tuple[str,...] = None, indexes: list[Index] = None):
        """
        An agnostic sogo database table representation. Each database manager must convert this class to their proper syntax

        :param name: Name of the table
        :type name: str
        :param columns: List od Column for this table
        :type columns: list[Column]
        :param primary_keys: Primary keys to set, defaults to None
        :type primary_keys: tuple[str,...], optional
        :param indexes: Index/Generated columns to make, defaults to None
        :type indexes: list[Index], optional
        """
        if not isinstance(name, str) or len(name) == 0:
            logger.error("Try to instantiate Table with no name")
        if not isinstance(columns, list) or len(columns) == 0:
            logger.error("Try to instantiate Table without column's list")

        if not re.match(REX_VALID_NAMES, name):
            logger.error("Try to instantiate Table an unvalid name: %s", name)

        self.name   = name
        self.columns = columns
        if primary_keys:
            for key in primary_keys:
                do_exist = False
                for col in self.columns:
                    if col.name == key:
                        do_exist = True
                        break
                if not do_exist:
                    logger.error("Try to instantiate Table with the primary key %s but is absent from columns %s", key, columns)

        self.primary_keys = primary_keys
        self.index = indexes
