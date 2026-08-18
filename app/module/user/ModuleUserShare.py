from __future__ import annotations
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.utils import errors as err
from app.utils.db.Condition import EqualCondition
from app.utils.exceptions import RequestException, AggravatedException
from app.utils.logger.logger import logger_user_profile
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL


class ModuleUserShare:
    """
    Module to handle user folders/shares (calendar and addressbook) in sogo_user_profiles table
    """

    def __init__(self, process_settings: ProcessSetting, domain_settings: dict):
        """
        Initialize the module with database connection

        :param process_settings: Process settings containing database configuration
        :type process_settings: ProcessSetting
        :param domain_settings: Domain settings dictionary
        :type domain_settings: dict
        """
        self.process_settings = process_settings

        sogo_db_type = f"Client{process_settings.SOGO_P_DB_TYPE}"

        self.sogo_db_manager: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=sogo_db_type,
            module_args=self.process_settings.get_db_settings()
        )

    def get_user_folders(self, uid: str) -> dict:
        """
        Get the folders column content for a user (contains calendar and addressbook keys)

        :param uid: User unique identifier
        :type uid: str
        :return: Folders dictionary containing CALENDAR and ADDRESSBOOKS structure
        :rtype: dict
        :raises RequestException: If user profile not found
        :raises AggravatedException: If multiple user profiles found
        """
        logger_user_profile.debug("Getting folders for uid: %s", uid)

        self.sogo_db_manager.connect()

        condition = EqualCondition(tbl.COL_USER_UID.name, uid)
        result = list(self.sogo_db_manager.select_from_table(
            table_name=tbl.TABLE_USER.name,
            column_tuple=(tbl.COL_USER_FOLDERS.name,),
            condition=condition
        ))

        if len(result) == 0:
            logger_user_profile.error("No user found for uid: %s", uid)
            raise RequestException(err.ERROR_USER_PROFILE_NOT_FOUND.m, err.ERROR_USER_PROFILE_NOT_FOUND)

        if len(result) > 1:
            logger_user_profile.error("Multiple users found for uid: %s", uid)
            raise AggravatedException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

        folders = result[0][0]
        logger_user_profile.debug("Successfully retrieved folders for uid: %s", uid)
        return folders if folders else {}
