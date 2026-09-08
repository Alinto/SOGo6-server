from __future__ import annotations
from typing import TYPE_CHECKING, cast, Any

from marshmallow import EXCLUDE, ValidationError

from app.config.db import tables as tbl
from app.config.settings.UserSettings import get_all_user_settings_schema, user_settings_dict
from app.config.settings.SogoSchema import check_data_for_sogo_schemas
from app.config.settings.DomainSettings import UserModuleSettingsObj, UserModuleSettings
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.db.Condition import EqualCondition
from app.utils.dict import merge_patch
from app.utils.exceptions import BugException, RequestException, AggravatedException
from app.utils.logger.logger import logger_user_profile
from app.utils.maths.sogo_hash import get_unique_token, HASH_SIZE_USER, HASH_SIZE_ACCOUNT
from app.utils.maths.crypto_utils import encrypt_password
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL
    from app.auth.User import User


class ModuleUserProfile:
    """
    Module to handle user profiles in sogo_user_profiles table
    """

    def __init__(self, process_settings: ProcessSetting, domain_settings: dict):
        """
        Initialize the module with database connection

        domain_settings can be either default_domain_settings or user_domain_settings
        
        :param process_settings: Process settings containing database configuration
        :type process_settings: ProcessSetting
        """
        self.process_settings = process_settings
        self.user_domain = domain_settings

        self.user_module_settings = UserModuleSettingsObj(domain_settings[UserModuleSettings.subparent])

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
            return True
        elif len(result) > 1:
            logger_user_profile.error("Multiple user profiles found for uid: %s", uid)
            raise AggravatedException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

        logger_user_profile.debug("No user profile found for uid: %s", uid)
        return False

    def create_user_profile(self, user: User) -> None:
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

        # Generate the main account with the main identity
        main_account = {
            "receipts": {},
            "certificates": {},
            "identities": [{
                "mail": user.mail,
                "name": user.cn,
                "replyTo": user.mail,
                "isDefault": True,
                "signatures": {}
            }]
        }

        # Generate the default preferences
        default_pref_by_admin = cast(dict[str, dict], self.user_domain.get("USER_DEFAULT", {}))
        preferences: dict[str, dict] = {}
        for user_schema in get_all_user_settings_schema():
            default_schema = user_schema()
            default_new: dict = {}
            if default_schema.subparent in default_pref_by_admin:
                try:
                    default_new = default_schema.load(default_pref_by_admin[user_schema.subparent], unknown=EXCLUDE)
                except ValidationError as e:
                    logger_user_profile.error("Default user settings set by admin are incorrect: %s\nContinue with true default", e)
                    default_new = default_schema.load({}, unknown=EXCLUDE)
            else:
                default_new = default_schema.load({}, unknown=EXCLUDE)

            preferences[default_schema.subparent] = default_new

        insert_values = [[
            user_hash,                    # hash
            user.uid,                          # uid
            preferences,                  # preferences
            {},                           # folders (will be updated after calendar/addressbook creation)
            main_account,                 # main_account (with default)
            {},                           # external_accounts (empty dict)
            None,                         # filters (nullable)
            "",                           # private_salt (empty)
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
            logger_user_profile.error("Exception while creating user profile for uid: %s - %s", user.uid, e)
            raise BugException(err.ERROR_USER_PROFILE_CREATION_FAILED.m, err.ERROR_USER_PROFILE_CREATION_FAILED) from e

        if row_inserted != 1:
            logger_user_profile.error("Failed to create user profile for uid: %s, rows inserted: %s", user.uid, row_inserted)
            raise BugException(err.ERROR_USER_PROFILE_INSERT_MISMATCH.m, err.ERROR_USER_PROFILE_INSERT_MISMATCH)

        logger_user_profile.info("Successfully created user profile for uid: %s", user.uid)

    def update_user_folders(self, uid: str, calendar_key: str, addressbook_key: str) -> None:
        """
        Update the folders column for a user with the personal calendar and addressbook keys.
        
        This is called during user onboarding after creating the personal calendar and addressbook.
        
        :param uid: User unique identifier
        :type uid: str
        :param calendar_key: Key of the personal calendar
        :type calendar_key: str
        :param addressbook_key: Key of the personal addressbook
        :type addressbook_key: str
        :raises RequestException: If user profile not found
        :raises BugException: If multiple user profiles found or update fails
        """
        logger_user_profile.debug("Updating folders for uid: %s with calendar_key: %s and addressbook_key: %s", 
                                  uid, calendar_key, addressbook_key)
        
        # Build the folders structure
        folders_data = {
            "CALENDAR": {
                "OWNER": {
                    calendar_key: True
                }
            },
            "ADDRESSBOOKS": {
                "OWNER": {
                    addressbook_key: True
                }
            }
        }
        
        # Use the generic _update_user_column method
        self._update_user_column(uid, tbl.COL_USER_FOLDERS.name, folders_data)

    def add_folder_key(self, uid: str, folder_type: str, key: str, owner_key: str = "OWNER") -> None:
        """
        Add a new calendar or addressbook key to the folders column of a user profile.
        
        This is called after creating a new calendar or addressbook. The folder_type can be
        "CALENDAR" or "ADDRESSBOOKS". The key is added to the specified owner_key section of that 
        folder type (default is "OWNER" for personal resources, but can be "EXT" for external ones).
        
        If the folders column doesn't exist or is empty, it initializes the structure.
        If the key already exists, it's overwritten (harmless for boolean flags).
        
        :param uid: User unique identifier
        :type uid: str
        :param folder_type: Type of folder - "CALENDAR" or "ADDRESSBOOKS"
        :type folder_type: str
        :param key: Key of the calendar or addressbook to add
        :type key: str
        :param owner_key: Owner section key - "OWNER" for personal, "EXT" for external, etc.
        :type owner_key: str
        :raises RequestException: If user profile not found
        :raises AggravatedException: If multiple user profiles found or update fails
        """
        logger_user_profile.debug("Adding folder key for uid: %s, folder_type: %s, owner_key: %s, key: %s", 
                                  uid, folder_type, owner_key, key)
        
        # Get current folders data
        current_folders = self._get_user_column(uid, tbl.COL_USER_FOLDERS.name)
        
        # Initialize structure if needed
        if not current_folders:
            current_folders = {
                "CALENDAR": {"OWNER": {}},
                "ADDRESSBOOKS": {"OWNER": {}}
            }
        
        # Ensure the folder type exists
        if folder_type not in current_folders:
            current_folders[folder_type] = {}
        
        # Ensure the owner_key exists within the folder type
        if owner_key not in current_folders[folder_type]:
            current_folders[folder_type][owner_key] = {}
        
        # Add the new key
        current_folders[folder_type][owner_key][key] = True
        
        # Update the database
        self._update_user_column(uid, tbl.COL_USER_FOLDERS.name, current_folders)

    def remove_folder_key(self, uid: str, folder_type: str, key: str, owner_key: str = "OWNER") -> None:
        """
        Remove a calendar or addressbook key from the folders column of a user profile.

        Symmetric counterpart of :meth:`add_folder_key`. This is a no-op (besides a debug log) if
        the folders column, folder_type, owner_key, or key don't exist.

        :param uid: User unique identifier
        :type uid: str
        :param folder_type: Type of folder - "CALENDAR" or "ADDRESSBOOKS"
        :type folder_type: str
        :param key: Key of the calendar or addressbook to remove
        :type key: str
        :param owner_key: Owner section key - "OWNER" for personal, "EXT"/"SUBS" for external/shared, etc.
        :type owner_key: str
        :raises RequestException: If user profile not found
        :raises AggravatedException: If multiple user profiles found or update fails
        """
        logger_user_profile.debug("Removing folder key for uid: %s, folder_type: %s, owner_key: %s, key: %s",
                                  uid, folder_type, owner_key, key)

        current_folders = self._get_user_column(uid, tbl.COL_USER_FOLDERS.name)

        if not current_folders:
            return

        if folder_type not in current_folders or owner_key not in current_folders[folder_type]:
            return

        if key not in current_folders[folder_type][owner_key]:
            return

        del current_folders[folder_type][owner_key][key]

        self._update_user_column(uid, tbl.COL_USER_FOLDERS.name, current_folders)

    def update_folder_value(self, uid: str, resource: str, folder_id: str, value: bool) -> dict:
        """
        Update the boolean value of a single folder key within the folders column (CALENDAR or ADDRESSBOOKS).

        Searches every owner-type sub-section (OWNER, SUBS, EXT, ...) of the given resource for folder_id
        and updates the first match found; folder_id is expected to be unique across the whole structure.

        :param uid: User unique identifier
        :type uid: str
        :param resource: Resource type - "CALENDAR" or "ADDRESSBOOKS"
        :type resource: str
        :param folder_id: Unique id of the folder to update
        :type folder_id: str
        :param value: New boolean value to set
        :type value: bool
        :return: The updated folders dictionary
        :rtype: dict
        :raises RequestException: If user profile not found or folder_id not found for this resource
        :raises AggravatedException: If multiple user profiles found
        """
        logger_user_profile.debug("Updating folder value for uid: %s, resource: %s, id: %s, value: %s",
                                  uid, resource, folder_id, value)

        current_folders = self._get_user_column(uid, tbl.COL_USER_FOLDERS.name)

        for section in current_folders.get(resource, {}).values():
            if folder_id in section:
                section[folder_id] = value
                self._update_user_column(uid, tbl.COL_USER_FOLDERS.name, current_folders)
                return current_folders

        logger_user_profile.error("Folder key not found for uid: %s, resource: %s, id: %s", uid, resource, folder_id)
        raise RequestException(err.ERROR_FOLDER_KEY_NOT_FOUND.m, err.ERROR_FOLDER_KEY_NOT_FOUND)

    def _get_user_column(self, uid: str, field_name: str) -> Any:
        """
        Generic method to get a specific field from user profile
        
        :param uid: User unique identifier
        :type uid: str
        :param field_name: Name of the field to retrieve
        :type field_name: str
        :return: Field value (dict, list, or empty dict if None)
        :rtype: Any
        :raises RequestException: If no user found (ERROR_USER_PROFILE_NOT_FOUND)
        :raises AggravatedException: If multiple users found (ERROR_USER_PROFILE_DUPLICATE)
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
            raise AggravatedException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

        field_value = result[0][0]
        return field_value if field_value else {}

    def _update_user_column(self, uid: str, field_name: str, field_value: Any) -> None:
        """
        Generic method to update a specific field in user profile
        
        :param uid: User unique identifier
        :type uid: str
        :param field_name: Name of the field to update
        :type field_name: str
        :param field_value: New value for the field (dict, list, or other type)
        :type field_value: Any
        :raises RequestException: If no user found (ERROR_USER_PROFILE_NOT_FOUND)
        :raises AggravatedException: If update affects unexpected number of rows
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
            raise AggravatedException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

        logger_user_profile.info("Successfully updated %s for uid: %s", field_name, uid)

    def _clean_main_account(self, user: User, main_account: dict) -> None:
        """
        Clean main_account by setting the right identity with the right values.
        Directly modifies main_account dict

        :param main_account: Contains the user main account
        :type main_account: dict
        """
        #Cleanup main account according to domain_settings restriction
        # If identities are disabled, only keep the original identity (should be at index 0)
        if not self.user_module_settings.SOGO_D_IDENTITIES_ENABLED:
            main_account["identities"] = [main_account["identities"][0]]
            #TODO check this is correct and ensure that original identity is at 0 when modifying main account

        # Apply field restrictions to all identities
        identities: list[dict] = main_account["identities"]
        for identity in identities:
            if not self.user_module_settings.SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED or not self.user_module_settings.SOGO_D_IDENTITIES_ENABLED:
                identity["mail"] = user.mail
            if not self.user_module_settings.SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED or not self.user_module_settings.SOGO_D_IDENTITIES_ENABLED:
                identity["name"] = user.cn
            if not self.user_module_settings.SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED or not self.user_module_settings.SOGO_D_IDENTITIES_ENABLED:
                identity["reply-to"] = user.mail

    def list_accounts(self, user: User) -> list:
        """
        List all external accounts for a user, including the main account as first element (id="0")
        
        :param uid: User unique identifier
        :type uid: str
        :return: List of all accounts with their data, including main account as first element
        :rtype: list
        :raises RequestException: If user profile not found
        :raises BugException: If multiple user profiles found
        """
        logger_user_profile.debug("Listing external accounts for uid: %s", user.uid)

        #Get Main Account
        main_account = self._get_user_column(user.uid, tbl.COL_USER_MAIN_ACCOUNT.name)

        #Cleanup main account according to domain_settings restriction
        self._clean_main_account(user, main_account)

        result = [{"id": "0", **main_account}]

        #Add external accounts
        if self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
            external_accounts: dict = self._get_user_column(user.uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)
            for account_hash, account_data in external_accounts.items():
                if "password" in account_data["mail_server"]:
                    account_data["mail_server"].pop("password")
                if "password" in account_data["mail_outgoing"]:
                    account_data["mail_outgoing"].pop("password")
                result.append({"id": account_hash, **account_data})

        return result

    def get_account_detail(self, user: User, account_id: str) -> dict:
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
        logger_user_profile.debug("Getting account %s for uid: %s", account_id, user.uid)

        # If account_id is "0", return the main account
        if account_id == "0":
            main_account: dict = self._get_user_column(user.uid, tbl.COL_USER_MAIN_ACCOUNT.name)
            self._clean_main_account(user, main_account)
            return main_account

        # Otherwise, retrieve external account
        external_accounts = self._get_user_column(user.uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)

        if account_id not in external_accounts:
            logger_user_profile.error("External account not found: %s for uid: %s", account_id, user.uid)
            raise RequestException(err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m, err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND)

        return external_accounts[account_id]

    def _validate_signatures_size_for_one_identity(self, identity: dict, size_limit: int) -> None:
        """
        Check all signatures size for one identity

        :param identity: identity dict
        :type identity: dict
        :raises RequestException: If the size limit is exceded
        """
        signatures: dict
        if signatures := identity.get("signatures", {}):
            for _, signature_value in signatures.items():
                if isinstance(signature_value, str) and len(signature_value.encode('utf-8')) > size_limit:
                    raise RequestException(
                        err.ERROR_SIGNATURE_SIZE_EXCEEDED.m,
                        err.ERROR_SIGNATURE_SIZE_EXCEEDED
                    ) 

    def _validate_signatures_size(self, identities: list[dict[str, Any]]) -> None:
        """Validate that all signatures in identities do not exceed the size limit (bytes).
        
        :param identities: List of identity dictionaries containing signatures
        :type identities: List[Dict[str, Any]]
        :raises RequestException: If any signature exceeds the size limit
        """
        size_limit = self.user_module_settings.SOGO_D_SIGNATURE_SIZE_LIMIT * 1024
        if size_limit <= 0:
            return  # No limit set

        for identity in identities:
            self._validate_signatures_size_for_one_identity(identity, size_limit)

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

        identities_list = account_data["identities"]
        self._validate_signatures_size(identities_list)

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

    def update_external_account(self, user: User, account_id: str, account_data: dict) -> dict:
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
        logger_user_profile.debug("Updating external account %s for uid: %s", account_id, user.uid)

        all_external_accounts = self._get_user_column(user.uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)

        if account_id not in all_external_accounts:
            logger_user_profile.error("External account not found: %s for uid: %s", account_id, user.uid)
            raise RequestException(err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m, err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND)

        external_account: dict = all_external_accounts[account_id]
        # Encrypt password of mail_server:
        mail_server: dict
        if mail_server := account_data.get("mail_server", None):
            password = mail_server.get("password", None)
            if password and len(password) > 0:
                mail_server["password"] = encrypt_password(password)

        # Encrypt password of mail_outgoing:
        mail_outgoing: dict
        if mail_outgoing := account_data.get("mail_outgoing", None):
            password = mail_outgoing.get("password", None)
            if password and len(password) > 0:
                mail_outgoing["password"] = encrypt_password(password)

        # Encrypt certificates
        #TODO

        print(f"Current content: {external_account}")
        print(f"Patch content: {account_data}")
        # Partial update: merge with existing data, all_external_accounts, being a mutable dict, will be changed automatically
        merge_patch(account_data, external_account)
        print(f"Result content: {external_account}")

        self._update_user_column(user.uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name, all_external_accounts)

        logger_user_profile.info("Successfully updated external account %s for uid: %s", account_id, user.uid)

        # Return the complete account data with the id field at the same level as other fields
        response_data = {
            "id": account_id, **external_account
        }

        return response_data

    def delete_external_account(self, user: User, account_id: str) -> None:
        """
        Delete an external account
        
        :param uid: User unique identifier
        :type uid: str
        :param account_id: Hash of the external account to delete
        :type account_id: str
        :raises RequestException: If account not found or user profile not found
        :raises BugException: If multiple user profiles found or update fails
        """
        logger_user_profile.debug("Deleting external account %s for uid: %s", account_id, user.uid)

        external_accounts: dict = self._get_user_column(user.uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name)

        if account_id not in external_accounts:
            logger_user_profile.error("External account not found: %s for uid: %s", account_id, user.uid)
            raise RequestException(err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m, err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND)

        external_accounts.pop(account_id, None)

        self._update_user_column(user.uid, tbl.COL_USER_EXTERNAL_ACCOUNTS.name, external_accounts)

        logger_user_profile.info("Successfully deleted external account %s for uid: %s", account_id, user.uid)


    def update_main_account(self, user: User, account_data: dict) -> dict:
        """
        Update the main account
        
        :param uid: User unique identifier
        :type uid: str
        :param account_data: Updated account data (partial update supported)
        :type account_data: dict
        :return: The updated main account data
        :rtype: dict
        :raises RequestException: If main account not found or user profile not found
        """
        logger_user_profile.debug("Updating main account for uid: %s", user.uid)


        #Check identities' rights
        all_identities = account_data.get("identities", None)
        if not all_identities:
            #Cannot delete identities (With merge_patch None means delete the parameter)
            raise RequestException(err.ERROR_USER_PROFILE_NO_IDENTITY.m, err.ERROR_USER_PROFILE_NO_IDENTITY)

        if not self.user_module_settings.SOGO_D_IDENTITIES_ENABLED:
            if len(all_identities) > 1:
                raise RequestException(err.ERROR_IDENTITIES_FORBIDDEN.m, err.ERROR_IDENTITIES_FORBIDDEN)

        size_limit = self.user_module_settings.SOGO_D_SIGNATURE_SIZE_LIMIT * 1024
        identity: dict
        for identity in all_identities:
            if not self.user_module_settings.SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED and \
                    identity["mail"] != user.mail:
                raise RequestException(err.ERROR_IDENTITIES_CUSTOM_FROM_FORBIDDEN.m, err.ERROR_IDENTITIES_CUSTOM_FROM_FORBIDDEN)
            if not self.user_module_settings.SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED and \
                    identity["name"] != user.cn:
                raise RequestException(err.ERROR_IDENTITIES_CUSTOM_NAME_FORBIDDEN.m, err.ERROR_IDENTITIES_CUSTOM_NAME_FORBIDDEN)
            if not self.user_module_settings.SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED and \
                    identity["reply-to"] != user.mail:
                raise RequestException(err.ERROR_IDENTITIES_CUSTOM_REPLY_TO_FORBIDDEN.m, err.ERROR_IDENTITIES_CUSTOM_REPLY_TO_FORBIDDEN)
            if size_limit > 0:
                self._validate_signatures_size_for_one_identity(identity, size_limit)

        #Encrypt certificates if needed
        #TODO

        #Get the main account data
        main_account = self._get_user_column(user.uid, tbl.COL_USER_MAIN_ACCOUNT.name)

        if not main_account:
            logger_user_profile.error("Main account not found for uid: %s", user.uid)
            raise AggravatedException(err.ERROR_MAIN_ACCOUNT_NOT_FOUND.m, err.ERROR_MAIN_ACCOUNT_NOT_FOUND)

        # Partial update: merge with existing data
        merge_patch(account_data, main_account)


        self._update_user_column(user.uid, tbl.COL_USER_MAIN_ACCOUNT.name, main_account)

        logger_user_profile.info("Successfully updated main account for uid: %s", user.uid)

        return {"id": "0", **main_account}

    def get_user_preferences(self, uid:str) -> dict:
        """
        Return the user preferences

        :param uid: _description_
        :type uid: str
        :return: _description_
        :rtype: dict
        """

        return self._get_user_column(uid, tbl.COL_USER_DEFAULTS.name)

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

        return self._get_user_column(uid, tbl.COL_USER_FOLDERS.name)

    def get_partial_user_preferences(self, uid:str, subparent:str) -> dict:
        """
        Return just a part of the user preferences

        :param uid: UID of the user
        :type uid: str
        :param subparent: Name of the subparent
        :type subparent: str
        :raises RequestException: _description_
        :return: _description_
        :rtype: dict
        """

        if subparent.lower() not in user_settings_dict:
            raise RequestException(f"Preferences asked {subparent} does not exist", err.ERROR_PREF_UNKNOWN_SUB)

        prefs = self._get_user_column(uid, tbl.COL_USER_DEFAULTS.name)
        real_subparent = user_settings_dict[subparent.lower()].subparent
        ret = {
            real_subparent: prefs.get(real_subparent, {})
        }
        return ret

    def update_user_preferences(self, uid:str, new_data:dict, subparent:str|None = None) -> dict:
        """
        Update all or a part of the user preferences

        :param uid: UID of the user
        :type uid: str
        :param new_data: new data to be merge patch
        :type new_data: dict
        :param subparent: if the new data is only one part, name of the part, leave to None if this is all preferences
        :type subparent: str | None, optional
        :return: the new value of user preferences
        :rtype: dict
        """
        current_data = self._get_user_column(uid, tbl.COL_USER_DEFAULTS.name)

        if subparent:
            real_subparent = user_settings_dict[subparent.lower()].subparent
            patch = {real_subparent: new_data}
        else:
            patch = new_data

        merge_patch(patch, current_data)

        new_data = check_data_for_sogo_schemas(current_data, get_all_user_settings_schema)

        self._update_user_column(uid, tbl.COL_USER_DEFAULTS.name, new_data)

        if subparent:
            real_subparent = user_settings_dict[subparent.lower()].subparent
            return new_data[real_subparent]
        return new_data

    def get_delegations_given(self, user: User) -> list[str]:
        """
        Get all delegations given by the user
        
        :param uid: User unique identifier
        :type uid: str
        :return: List of email addresses that have delegation
        :rtype: list[str]
        :raises RequestException: If user profile not found
        :raises BugException: If multiple user profiles found
        """
        logger_user_profile.debug("Getting delegations given for uid: %s", user.uid)

        delegations = self._get_user_column(user.uid, tbl.COL_USER_DELEGATION_GIVEN.name)

        # Ensure we return a list (handle None or empty dict)
        if not delegations or not isinstance(delegations, list):
            return []

        return delegations

    def add_delegation_given(self, user: User, delegate_email: str) -> str:
        """
        Add delagation rights to user
        
        """
        raise NotImplementedError()
        # """
        # Add a delegation to another user

        # :param uid: User unique identifier
        # :type uid: str
        # :param delegate_email: Email address of the user to grant delegation
        # :type delegate_email: str
        # :return: The delegate email address
        # :rtype: str
        # :raises RequestException: If user profile not found or delegation already exists
        # :raises BugException: If multiple user profiles found or update fails
        # """
        # logger_user_profile.debug("Adding delegation given for uid: %s to %s", user.uid, delegate_email)

        # delegations_data = self._get_user_column(user.uid, tbl.COL_USER_DELEGATION_GIVEN.name)

        # # Ensure delegations is a list (handle None, empty dict, or actual list)
        # delegations: list[str] = []
        # if delegations_data and isinstance(delegations_data, list):
        #     delegations = delegations_data

        # # Check if delegation already exists (case-insensitive)
        # delegate_email_lower = delegate_email.lower()
        # if any(email.lower() == delegate_email_lower for email in delegations):
        #     logger_user_profile.error("Delegation already exists: %s for uid: %s", delegate_email, user.uid)
        #     raise RequestException(err.ERROR_DELEGATION_ALREADY_EXISTS.m, err.ERROR_DELEGATION_ALREADY_EXISTS)

        # # Add the delegation
        # delegations.append(delegate_email)

        # self._update_user_column(user.uid, tbl.COL_USER_DELEGATION_GIVEN.name, delegations)

        # logger_user_profile.info("Successfully added delegation for uid: %s to %s", uid, delegate_email)

        # return delegate_email

    def get_user_profile(self, user:User) -> None:
        """
        Set the user profile dict for instance user

        :param user: The user to set
        :type user: User
        """
        self.sogo_db_manager.connect()

        columns = tuple(tbl.TABLE_USER.columns_name.keys())
        condition = EqualCondition(tbl.COL_USER_UID.name, user.uid)
        result = list(self.sogo_db_manager.select_from_table(
            table_name=tbl.TABLE_USER.name,
            column_tuple=columns,
            condition=condition
        ))

        if len(result) == 0:
            logger_user_profile.error("No user found for uid: %s when retrieving their profile", user.uid)
            raise RequestException(err.ERROR_USER_PROFILE_NOT_FOUND.m, err.ERROR_USER_PROFILE_NOT_FOUND)

        if len(result) > 1:
            logger_user_profile.error("Multiple users found for uid: %s when retrieving their profile", user.uid)
            raise AggravatedException(err.ERROR_USER_PROFILE_DUPLICATE.m, err.ERROR_USER_PROFILE_DUPLICATE)

        row = result[0]
        for idx, column_name in enumerate(columns):
            try:
                getattr(user.profile, column_name)
            except AttributeError as e:
                raise AggravatedException(err.ERROR_USER_PROFILE_MISMATCH_CLASS_DB.m, err.ERROR_USER_PROFILE_MISMATCH_CLASS_DB) from e
            setattr(user.profile, column_name, row[idx])
