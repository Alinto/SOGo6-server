from __future__ import annotations
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.utils.db.Condition import EqualCondition
from app.utils.exceptions import BugException
from app.utils.logger.logger import logger
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.maths.sogo_hash import get_unique_token, HASH_SIZE_USER
from app.utils import errors as err

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL

DEFAULT_IDENTITY_KEY_VALUE = 0

class ModuleUserProfile:
    """
    Module to handle user profiles in sogo_user_profiles table
    """

    def __init__(self, process_settings: ProcessSetting):
        """
        Initialize the module with database connection
        
        :param process_settings: Process settings containing database configuration
        :type process_settings: ProcessSetting
        """
        self.process_settings = process_settings
        sogo_db_type = f"Client{process_settings.SOGO_P_DB_TYPE}"

        self.sogo_db_manager: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=sogo_db_type,
            module_args=self.process_settings.get_db_settings()
        )

    def is_user_profile_present(self, uid: str) -> bool:
        """
        Check if a user already exists in the database
        
        :param uid: User unique identifier (full email)
        :type uid: str
        :return: True if user exists, False otherwise
        :rtype: bool
        """
        self.sogo_db_manager.connect()

        condition = EqualCondition(tbl.COL_USER_UID.name, uid)
        result = list(self.sogo_db_manager.select_from_table(
            table_name=tbl.TABLE_USER.name,
            column_tuple=(tbl.COL_USER_UID.name,),
            condition=condition
        ))
        if len(result) == 1:
            logger.debug("User profile found for uid: %s", uid)
        elif len(result) > 1:
            logger.error("Multiple user profiles found for uid: %s", uid)
            raise BugException(f"Multiple user profiles found for uid: {uid}", err.ERROR_USER_PROFILE_DUPLICATE)
        else:
            logger.debug("No user profile found for uid: %s", uid)
        return len(result) == 1

    def create_user_profile(self, uid: str, contact_info: dict) -> None:
        """
        Create a new user profile in the database with default values
        
        :param uid: User unique identifier (full email)
        :type uid: str
        :param contact_info: Contact information from user source (uid, cn, email)
        :type contact_info: dict
        """
        self.sogo_db_manager.connect()

        # Generate unique hash for this user
        user_hash = get_unique_token(HASH_SIZE_USER)

        main_account = {
            "receipts": {},
            "certificates": {},
            DEFAULT_IDENTITY_KEY_VALUE: {
                "mail": contact_info.get("email", uid),
                "name": contact_info.get("cn", uid),
                "replyTo": contact_info.get("replyTo", uid),
                "isDefault": True,
                "signatures": []
            }
        }

        insert_values = [[
            user_hash,                    # hash
            uid,                          # uid
            {},                           # preferences (empty dict)
            {},                           # folders (empty dict)
            main_account,                 # main_account (with default)
            {},                           # external_accounts (empty dict)
            None,                         # filters (nullable)
            "",                           # private_salt (empty)
            None,                         # acl_given (nullable)
            None,                         # acl_received (nullable)
            None,                         # delegation_given (nullable)
            None                          # delegation_received (nullable)
        ]]

        columns = (
            tbl.COL_HASH.name,
            tbl.COL_USER_UID.name,
            tbl.COL_USER_DEFAULTS.name,
            tbl.COL_USER_FOLDERS.name,
            tbl.COL_USER_MAIN_ACCOUNT.name,
            tbl.COL_USER_EXTERNAL_ACCOUNTS.name,
            tbl.COL_USER_FILTERS.name,
            tbl.COL_USER_PRIVATE_SALT.name,
            tbl.COL_USER_ACL_GIVEN.name,
            tbl.COL_USER_ACL_GOT.name,
            tbl.COL_USER_DELEGATION_GIVEN.name,
            tbl.COL_USER_DELEGATION_GOT.name
        )

        try:
            row_inserted = self.sogo_db_manager.insert_in_table(
                table_name=tbl.TABLE_USER.name,
                column_tuple=columns,
                values_tuple=insert_values
            )
        except Exception as e:
            logger.error("Exception while creating user profile for uid: %s - %s", uid, e)
            raise BugException(f"Exception while creating user profile: {e}", err.ERROR_USER_PROFILE_CREATION_FAILED) from e

        if row_inserted != 1:
            logger.error("Failed to create user profile for uid: %s, rows inserted: %s", uid, row_inserted)
            raise BugException(f"Failed to create user profile, rows inserted: {row_inserted}, should be 1", err.ERROR_USER_PROFILE_INSERT_MISMATCH)

        logger.info("Successfully created user profile for uid: %s", uid)
