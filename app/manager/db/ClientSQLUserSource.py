
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Generator

from app.manager.user_source.ClientUserSource import ClientUserSource
from app.utils import constants as cs
from app.utils import errors as err
from app.utils import exceptions as exc
from app.utils.db import Condition
from app.utils.maths.crypto_common import check_password
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_sql
from app.utils.strings import SecretString


if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL

DB_MAPPING = {
    "postgresql": "ClientPostgreSQL",
    "mysql": "ClientMySQL"
}

def parse_db_user_record(record: dict[str, Any]) -> dict[str, list[str]]:
    """
    Db record return values as string, or int. Just transform them into strings

    :param record: _description_
    :type record: tuple[str, dict[str, list[bytes]]]
    :rtype: _type_
    """
    user_dict: dict[str, list[str]] = {}
    for attribute, values in record.items():
        user_dict[attribute] = [values]
    return user_dict

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
                    db_pwd_algo:str,
                    db_search:list[str],
                    db_filter: Condition.Condition|None = None,):
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
        self.db_filter = db_filter
        self.db_search = db_search

    def connect(self) -> None:
        self.client_sql.connect()

    def check_login(self, username: str, password: str, domain:str) -> tuple[bool, dict, dict[str, list[str]]]:
        """
        Check the credentials of a usermary
        
        Returns a tuple:
        * bool, True if the login has been successful
        * dict, Extra info for the login/passwword policy
        * dict, contact Info

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
        cond: Condition.Condition = Condition.EqualCondition(self.uid_field, username)
        if self.db_filter:
            cond = Condition.AndCondition(cond, self.db_filter)

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
        #Get encrypted password
        if not self.pwd_field in user:
            raise exc.AggravatedException(f"Column for password missingn {self.pwd_field}", err.ERROR_US_DB_MISSING_PWD)
        encrypted_password = user[self.pwd_field]

        match = check_password(password, encrypted_password, self.pwd_algo)
        if match:
            return True, {}, parse_db_user_record(user)
        
        return False, {}, {}

    def search_user(self, search: str, extra_condition: Condition.Condition, limit:int, username:str, domain:str, password:str) -> Generator[dict[str, list[str]]]:
        """
        Search users for autocompletion, max 100 entries

        :param search: String to search
        :type search: str
        :param extra_condition: extra conditions for autocompletion
        :type extra_condition: Condition
        :return: infos of the user
        :rtype: dict[str, list[str]]
        """
        # Get the table columns
        table_info = self.client_sql.get_table_info(self.db_table)
        if not table_info:
            raise exc.AggravatedException(error=err.ERROR_US_DB_MISSING_TABLE)
        columns_name = list(table_info.keys())

        #Merge db_filter with extra condition
        if self.db_filter:
            extra_condition = Condition.AndCondition(self.db_filter, extra_condition)

        raws = self.client_sql.select_from_table(self.db_table, column_tuple=("*",), condition=extra_condition, limit=limit)
        for record in raws:
            user = dict(zip(columns_name, record))
            yield parse_db_user_record(user)

    def get_user_info(self, uid:str, extra_condition:Condition.Condition, username:str, domain:str, password:str) -> dict[str, list[str]]:
        """
        Get info for a user or an empty dict if the user is not found/does not exist

        :param uid: _description_
        :type uid: str
        :param extra_condition: _description_
        :type extra_condition: Condition
        :param username: _description_
        :type username: str
        :param domain: _description_
        :type domain: str
        :param password: _description_
        :type password: str
        :return: _description_
        :rtype: dict[str, list[str]]
        """
        # Get the table columns
        table_info = self.client_sql.get_table_info(self.db_table)
        if not table_info:
            raise exc.AggravatedException(error=err.ERROR_US_DB_MISSING_TABLE)
        columns_name = list(table_info.keys())

        #Merge db_filter with extra condition
        if self.db_filter:
            extra_condition = Condition.AndCondition(self.db_filter, extra_condition)

        raws = list(self.client_sql.select_from_table(self.db_table, column_tuple=("*",), condition=extra_condition))

        if n := len(raws) == 1:
            user = dict(zip(columns_name, raws[0]))
            return parse_db_user_record(user)
        elif n > 1:
            raise exc.AggravatedException(f"More than one user returns for the uid {uid}", err.ERROR_US_NOT_UNIQUE_USER)

        return {}
