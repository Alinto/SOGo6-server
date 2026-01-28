from __future__ import annotations
from typing import TYPE_CHECKING

from app.config.db import tables as tbl
from app.utils.db.Condition import EqualCondition
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_user_profile
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.maths.sogo_hash import get_unique_token, HASH_SIZE_USER, HASH_SIZE_ACCOUNT
from app.utils import errors as err
from app.utils.maths.crypto_utils import encrypt_password

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL


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
        
        :param uid: User unique identifier
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
            logger_user_profile.debug("User profile found for uid: %s", uid)
        elif len(result) > 1:
            logger_user_profile.error("Multiple user profiles found for uid: %s", uid)
            raise BugException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)
        else:
            logger_user_profile.debug("No user profile found for uid: %s", uid)
        return len(result) == 1

    def create_user_profile(self, uid: str, contact_info: dict) -> None:
        """
        Create a new user profile in the database with default values
        
        :param uid: User unique identifier
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
            "identities": [{
                "mail": contact_info.get("email", uid),
                "name": contact_info.get("cn", uid),
                "replyTo": contact_info.get("replyTo", uid),
                "isDefault": True,
                "signatures": {}
            }]
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
        except BugException as e:
            logger_user_profile.error("Exception while creating user profile for uid: %s - %s", uid, e)
            raise BugException(err.ERROR_USER_PROFILE_CREATION_FAILED.m, err.ERROR_USER_PROFILE_CREATION_FAILED) from e

        if row_inserted != 1:
            logger_user_profile.error("Failed to create user profile for uid: %s, rows inserted: %s", uid, row_inserted)
            raise BugException(err.ERROR_USER_PROFILE_INSERT_MISMATCH.m, err.ERROR_USER_PROFILE_INSERT_MISMATCH)

        logger_user_profile.info("Successfully created user profile for uid: %s", uid)

    def _get_user_column(self, uid: str, field_name: str) -> dict:
        """
        Generic method to get a specific field from user profile
        
        :param uid: User unique identifier
        :type uid: str
        :param field_name: Name of the field to retrieve
        :type field_name: str
        :return: Field value (dict or empty dict if None)
        :rtype: dict
        :raises RequestException: If no user found (ERROR_USER_PROFILE_NOT_FOUND)
        :raises BugException: If multiple users found (ERROR_USER_PROFILE_DUPLICATE)
        """
        self.sogo_db_manager.connect()

        condition = EqualCondition(tbl.COL_USER_UID.name, uid)
        result = list(self.sogo_db_manager.select_from_table(
            table_name=tbl.TABLE_USER.name,
            column_tuple=(field_name,),
            condition=condition
        ))

        if len(result) == 0:
            logger_user_profile.error("No user found for uid: %s when retrieving field: %s", uid, field_name)
            raise RequestException(err.ERROR_USER_PROFILE_NOT_FOUND.m, err.ERROR_USER_PROFILE_NOT_FOUND)

        if len(result) > 1:
            logger_user_profile.error("Multiple users found for uid: %s when retrieving field: %s", uid, field_name)
            raise BugException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

        field_value = result[0][0]
        return field_value if field_value else {}

    def _update_user_column(self, uid: str, field_name: str, field_value: dict) -> None:
        """
        Generic method to update a specific field in user profile
        
        :param uid: User unique identifier
        :type uid: str
        :param field_name: Name of the field to update
        :type field_name: str
        :param field_value: New value for the field
        :type field_value: dict
        :raises BugException: If update affects unexpected number of rows
        """
        self.sogo_db_manager.connect()

        condition = EqualCondition(tbl.COL_USER_UID.name, uid)

        row_updated = self.sogo_db_manager.update_in_table(
            table_name=tbl.TABLE_USER.name,
            column_tuple=(field_name,),
            values_list=[field_value],
            condition=condition
        )

        if row_updated == 0:
            logger_user_profile.error("No user found for uid: %s when updating field: %s", uid, field_name)
            raise RequestException(err.ERROR_USER_PROFILE_NOT_FOUND.m, err.ERROR_USER_PROFILE_NOT_FOUND)

        if row_updated > 1:
            logger_user_profile.error("Multiple users found for uid: %s when updating field: %s", uid, field_name)
            raise BugException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

        logger_user_profile.info("Successfully updated %s for uid: %s", field_name, uid)

    def list_accounts(self, uid: str) -> list:
        """
        List all external accounts for a user, including the main account as first element (id="0")
        
        :param uid: User unique identifier
        :type uid: str
        :return: List of all accounts with their data, including main account as first element
        :rtype: list
        :raises RequestException: If user profile not found
        :raises BugException: If multiple user profiles found
        """
        logger_user_profile.debug("Listing external accounts for uid: %s", uid)

        external_accounts = self._get_user_column(uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)
        main_account = self._get_user_column(uid, tbl.COL_USER_MAIN_ACCOUNT.name)

        # Create list with main account first (with id "0"), followed by external accounts
        result = [{"id": "0", **main_account}]
        for account_hash, account_data in external_accounts.items():
            result.append({"id": account_hash, **account_data})

        return result

    def get_account_detail(self, uid: str, account_id: str) -> dict:
        """
        Get a specific external account by its hash, or main account if account_id is "0"
        
        :param uid: User unique identifier
        :type uid: str
        :param account_id: Hash of the external account, or "0" for main account
        :type account_id: str
        :return: External account data or main account data
        :rtype: dict
        :raises RequestException: If account not found or user profile not found
        :raises BugException: If multiple user profiles found
        """
        logger_user_profile.debug("Getting account %s for uid: %s", account_id, uid)

        # If account_id is "0", return the main account
        if account_id == "0":
            return self._get_user_column(uid, tbl.COL_USER_MAIN_ACCOUNT.name)

        # Otherwise, retrieve external account
        external_accounts = self._get_user_column(uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)

        if account_id not in external_accounts:
            logger_user_profile.error("External account not found: %s for uid: %s", account_id, uid)
            raise RequestException(err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m, err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND)

        return external_accounts[account_id]

    def create_external_account(self, uid: str, account_data: dict) -> dict:
        """
        Create a new external account for a user
        
        :param uid: User unique identifier
        :type uid: str
        :param account_data: External account data containing:
            - name: Account name
            - mail_server: Mail server configuration
            - mail_outgoing: Outgoing mail server configuration
            - identities: List of identities
            - receipts: Optional receipts (default empty)
            - certificates: Optional certificates (default empty)
        :type account_data: dict
        :return: Complete account data including the generated account_id
        :rtype: dict
        :raises RequestException: If user profile not found
        :raises BugException: If multiple user profiles found or update fails
        """
        logger_user_profile.debug("Creating external account for uid: %s", uid)

        external_accounts = self._get_user_column(uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)

        # Generate a unique account hash
        account_id = get_unique_token(HASH_SIZE_ACCOUNT)

        # Ensure the generated hash is unique with a limit to prevent infinite loop
        max_retries = 10
        retry_count = 0
        while account_id in external_accounts:
            retry_count += 1
            if retry_count >= max_retries:
                logger_user_profile.error("Max retries reached for hash generation for uid: %s", uid)
                raise BugException(err.ERROR_EXTERNAL_ACCOUNT_HASH_CONFLICT.m, err.ERROR_EXTERNAL_ACCOUNT_HASH_CONFLICT)
            logger_user_profile.warning("Account ID collision detected, generating new hash for uid: %s (attempt %d/%d)", uid, retry_count, max_retries)
            account_id = get_unique_token(HASH_SIZE_ACCOUNT)

        # Transform identities from list to dict with generated hashes
        identities_list = account_data.get("identities", [])

        # Build the account structure for storage
        account = {
            "name": account_data.get("name", ""),
            "mail_server": account_data.get("mail_server", {}),
            "mail_outgoing": account_data.get("mail_outgoing", {}),
            "identities": identities_list,
            "receipts": account_data.get("receipts", {}),
            "certificates": account_data.get("certificates", {})
        }

        # Encrypt passwords using AES-256
        if "password" in account["mail_server"] and account["mail_server"]["password"]:
            account["mail_server"]["password"] = encrypt_password(account["mail_server"]["password"])

        if "password" in account["mail_outgoing"] and account["mail_outgoing"]["password"]:
            account["mail_outgoing"]["password"] = encrypt_password(account["mail_outgoing"]["password"])

        external_accounts[account_id] = account

        self._update_user_column(uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name, external_accounts)

        logger_user_profile.info("Successfully created external account %s for uid: %s", account_id, uid)

        # Return the complete account data with the id field at the same level as other fields
        response_data = {
            "id": account_id,
            "name": account.get("name"),
            "mail_server": account.get("mail_server"),
            "mail_outgoing": account.get("mail_outgoing"),
            "identities": account.get("identities"),
            "receipts": account.get("receipts"),
            "certificates": account.get("certificates")
        }

        return response_data

    def update_external_account(self, uid: str, account_id: str, account_data: dict) -> dict:
        """
        Update an existing external account
        
        :param uid: User unique identifier
        :type uid: str
        :param account_id: Hash of the external account to update
        :type account_id: str
        :param account_data: Updated account data (partial update supported)
        :type account_data: dict
        :return: The updated account data with id
        :rtype: dict
        :raises RequestException: If account not found or user profile not found
        :raises BugException: If multiple user profiles found or update fails
        """
        logger_user_profile.debug("Updating external account %s for uid: %s", account_id, uid)

        external_accounts = self._get_user_column(uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)

        if account_id not in external_accounts:
            logger_user_profile.error("External account not found: %s for uid: %s", account_id, uid)
            raise RequestException(err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m, err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND)

        # Partial update: merge with existing data
        current_account = external_accounts[account_id]

        # Update top-level fields if provided
        for key in ["name", "receipts", "certificates", "identities"]:
            if key in account_data:
                if isinstance(account_data[key], dict) and isinstance(current_account.get(key), dict):
                    # Deep merge for dict fields
                    current_account[key].update(account_data[key])
                else:
                    current_account[key] = account_data[key]

        # Handle mail_server with detailed update
        if "mail_server" in account_data:
            if not isinstance(current_account.get("mail_server"), dict):
                current_account["mail_server"] = {}

            for field, value in account_data["mail_server"].items():
                if field == "password" and value:
                    # Encrypt password before storing
                    current_account["mail_server"][field] = encrypt_password(value)
                else:
                    current_account["mail_server"][field] = value

        # Handle mail_outgoing with detailed update
        if "mail_outgoing" in account_data:
            if not isinstance(current_account.get("mail_outgoing"), dict):
                current_account["mail_outgoing"] = {}

            for field, value in account_data["mail_outgoing"].items():
                if field == "password" and value:
                    # Encrypt password before storing
                    current_account["mail_outgoing"][field] = encrypt_password(value)
                else:
                    current_account["mail_outgoing"][field] = value

        external_accounts[account_id] = current_account

        self._update_user_column(uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name, external_accounts)

        logger_user_profile.info("Successfully updated external account %s for uid: %s", account_id, uid)

        # Return the complete account data with the id field at the same level as other fields
        response_data = {
            "id": account_id,
            "name": current_account.get("name"),
            "mail_server": current_account.get("mail_server"),
            "mail_outgoing": current_account.get("mail_outgoing"),
            "identities": current_account.get("identities"),
            "receipts": current_account.get("receipts"),
            "certificates": current_account.get("certificates")
        }

        return response_data

    def delete_external_account(self, uid: str, account_id: str) -> None:
        """
        Delete an external account
        
        :param uid: User unique identifier
        :type uid: str
        :param account_id: Hash of the external account to delete
        :type account_id: str
        :raises RequestException: If account not found or user profile not found
        :raises BugException: If multiple user profiles found or update fails
        """
        logger_user_profile.debug("Deleting external account %s for uid: %s", account_id, uid)

        external_accounts = self._get_user_column(uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)

        if account_id not in external_accounts:
            logger_user_profile.error("External account not found: %s for uid: %s", account_id, uid)
            raise RequestException(err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m, err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND)

        del external_accounts[account_id]

        self._update_user_column(uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name, external_accounts)

        logger_user_profile.info("Successfully deleted external account %s for uid: %s", account_id, uid)

    def update_main_account(self, uid: str, account_data: dict) -> dict:
        """
        Update the main account
        
        :param uid: User unique identifier
        :type uid: str
        :param account_data: Updated account data (partial update supported)
        :type account_data: dict
        :return: The updated main account data
        :rtype: dict
        :raises RequestException: If main account not found or user profile not found
        :raises BugException: If multiple user profiles found or update fails
        """
        logger_user_profile.debug("Updating main account for uid: %s", uid)

        main_account = self._get_user_column(uid, tbl.COL_USER_MAIN_ACCOUNT.name)

        if not main_account:
            logger_user_profile.error("Main account not found for uid: %s", uid)
            raise RequestException(err.ERROR_MAIN_ACCOUNT_NOT_FOUND.m, err.ERROR_MAIN_ACCOUNT_NOT_FOUND)

        # Partial update: merge with existing data
        current_account = main_account

        # Update top-level fields if provided
        for key in ["name", "receipts", "certificates", "identities"]:
            if key in account_data:
                if isinstance(account_data[key], dict) and isinstance(current_account.get(key), dict):
                    # Deep merge for dict fields
                    current_account[key].update(account_data[key])
                else:
                    current_account[key] = account_data[key]

        # Handle mail_server with detailed update
        if "mail_server" in account_data:
            if not isinstance(current_account.get("mail_server"), dict):
                current_account["mail_server"] = {}

            for field, value in account_data["mail_server"].items():
                if field == "password" and value:
                    # Encrypt password before storing
                    current_account["mail_server"][field] = encrypt_password(value)
                else:
                    current_account["mail_server"][field] = value

        # Handle mail_outgoing with detailed update
        if "mail_outgoing" in account_data:
            if not isinstance(current_account.get("mail_outgoing"), dict):
                current_account["mail_outgoing"] = {}

            for field, value in account_data["mail_outgoing"].items():
                if field == "password" and value:
                    # Encrypt password before storing
                    current_account["mail_outgoing"][field] = encrypt_password(value)
                else:
                    current_account["mail_outgoing"][field] = value

        self._update_user_column(uid, tbl.COL_USER_MAIN_ACCOUNT.name, current_account)

        logger_user_profile.info("Successfully updated main account for uid: %s", uid)

        return {"id": "0", **current_account}
