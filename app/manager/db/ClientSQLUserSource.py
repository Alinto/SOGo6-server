
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Generic

from app.manager.user_source.ClientUserSource import ClientUserSource
from app.utils import constants as cs
from app.utils import errors as err
from app.utils import exceptions as exc
from app.utils.db import Condition
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_sql
from app.utils.strings import SecretString

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL

class ClientSQLUserSOurce(ClientUserSource):
    """
    Client for User Sources that use sql protocol (Mariadb, Postgresql...)
    """
    def __init__(self, db_type: str, db_param: dict):
        """
        _summary_
        """
        super().__init__()
        self.client_sql: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=db_type,
            module_args=db_param,
        )
    
    def connect(self) -> None:
        self.client_sql.connect()
