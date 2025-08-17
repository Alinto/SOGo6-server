import re

from app.utils.logger.logger import logger

REX_VALID_NAMES = r"^[A-Za-z_0-9]+$" #We force the fact that tables and columns' name must be alphanumerical with underscore only

SOGO_DB_DATA_TYPE = {"dict", "str", "list", "serial", "json"}
SOGO_DB_DATA_TYPE_VALIDATION = {
    "dict":   {"dict", "json"} ,
    "str":    {"str"},
    "list":   {"list"},
    "serial": {"serial", "int"},
    "json":   {"dict", "json"}
}

class Column:
    """
    Is a common db class. Each db manager will convert this column properly to their own dbapi

    """
    def __init__(self, name: str, data_type: str, is_nullable: bool = False, extra_agrs: dict = None):
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
        self.extra_args      = extra_agrs

class Index:
    """
    Is a common db class. Each db manager will convert this index properly to their own dbapi
    """
    def __init__(self):
        pass

class Table:
    """
    Is a common db class. Each db manager will convert this table properly to their own dbapi
    """

    def __init__(self, name: str, columns: list[Column], primary_key: str = None, indexes: list[Index] = None):
        if not isinstance(name, str) or len(name) == 0:
            logger.error("Try to instantiate Table with no name")
        if not isinstance(columns, list) or len(columns) == 0:
            logger.error("Try to instantiate Table without column's list")

        if not re.match(REX_VALID_NAMES, name):
            logger.error("Try to instantiate Table an unvalid name: %s", name)

        self.name   = name
        self.columns = columns
        if primary_key:
            do_exist = False
            for col in self.columns:
                if col.name == primary_key:
                    do_exist = True
                    break
            if not do_exist:
                logger.error("Try to instantiate Table with the primary key %s but is absent from columns %s", primary_key, columns)

        self.primary_key = primary_key
        self.index = indexes
