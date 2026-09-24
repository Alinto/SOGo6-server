
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

DB_MAPPING = {
    "postgresql": "ClientPostgreSQL",
    "mysql": "ClientMySQL"
}

class ClientSQLUserSource(ClientUserSource):
    """
    Client for User Sources that use sql protocol (Mariadb, Postgresql...)
    """
    def __init__(self, db_type: str, db_param: dict,
                    db_table: str,
                    db_uid: str,
                    db_mails: list[str],
                    db_cn: str,
                    db_pwd: str,
                    db_ou: str,
                    db_pwd_algo:str):
        """
        _summary_
        """
        super().__init__()
        self.client_sql: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=DB_MAPPING[db_type],
            module_args=db_param,
        )
        self.db_table = db_table
        self.uid_field = db_uid
        self.cn_field = db_cn
        self.mail_fields = db_mails
        self.pwd_field = db_pwd
        self.ou_field = db_ou
        self.pwd_algo = db_pwd_algo

    
    def connect(self) -> None:
        self.client_sql.connect()

    def check_login(self, username: str, password: str, domain:str) -> tuple[bool, dict, dict[str, list[str]]]:
        """
        _summary_

        :param username: _description_
        :type username: str
        :param password: _description_
        :type password: str
        :param domain: _description_
        :type domain: str
        :return: _description_
        :rtype: tuple[bool, dict, dict[str, list[str]]]
        """
        # Create the condition
        cond = Condition.EqualCondition(self.uid_field, username)

        # Get the table columns
        table_info = self.client_sql.get_table_info(self.db_table)
        if not table_info:
            raise exc.AggravatedException(error=err.ERROR_US_DB_MISSING_TABLE)
        columns_name = list(table_info.keys())

        # Get the password in the database
        ret = list(self.client_sql.select_from_table(self.db_table, column_tuple=("*",), condition=cond))

        size = len(ret)
        if size == 0:
            return False, {}, {}
        if size > 1:
            raise exc.AggravatedException("More than one user returns for the login", err.ERROR_US_NOT_UNIQUE_USER)

        user = dict(zip(columns_name, ret[0]))
        print(user)

        return False, {}, {}

