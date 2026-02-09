from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, List, Union, Tuple, Optional

from flask import request

from app.config.settings.DomainSettings import UserModuleSettings, UserModuleSettingsObj
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.exceptions import RequestException, BugException
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils import errors as err
from app.utils import constants as cs
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User


class InterfaceApiMailMailbox:
    """
    Interface for mailbox-related mail operations.

    Handles mail mailbox operations for one or multiple configured IMAP accounts.
    """

    def __init__(
        self,
        process_setting: ProcessSetting,
        user: User,
        user_domain: Dict
    ) -> None:
        self.process_setting = process_setting
        self.user = user
        self.user_module_settings = UserModuleSettingsObj(user_domain[UserModuleSettings.subparent])
        self.module_user_profile = ModuleUserProfile(process_setting, user_domain)

    def _is_external_account_allowed(self) -> bool:
        """Check if external mail accounts are allowed for this domain.
        
        :return: True if external accounts are allowed, False otherwise
        :rtype: bool
        """
        return self.user_domain.get("USER_MODULE_SETTINGS", {}).get("SOGO_D_ALLOW_EXT_MAIL_ACCOUNT", True) #TODO: default to True?

    def _is_identities_enabled(self) -> bool:
        """Check if identities are enabled for this domain.
        
        :return: True if identities are enabled, False otherwise
        :rtype: bool
        """
        return self.user_domain.get("USER_MODULE_SETTINGS", {}).get("SOGO_D_IDENTITIES_ENABLED", True)

    def _is_custom_from_enabled(self) -> bool:
        """Check if custom 'from' email in identities is allowed for this domain.
        
        :return: True if custom from is allowed, False otherwise
        :rtype: bool
        """
        return self.user_domain.get("USER_MODULE_SETTINGS", {}).get("SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED", True)

    def _is_custom_name_enabled(self) -> bool:
        """Check if custom name in identities is allowed for this domain.
        
        :return: True if custom name is allowed, False otherwise
        :rtype: bool
        """
        return self.user_domain.get("USER_MODULE_SETTINGS", {}).get("SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED", True)

    def _is_custom_reply_to_enabled(self) -> bool:
        """Check if custom reply-to email in identities is allowed for this domain.
        
        :return: True if custom reply-to is allowed, False otherwise
        :rtype: bool
        """
        return self.user_domain.get("USER_MODULE_SETTINGS", {}).get("SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED", True)

    def _get_signature_size_limit(self) -> int:
        """Get the maximum signature size limit for this domain.
        
        :return: Maximum signature size in bytes, 0 means no limit
        :rtype: int
        """
        size_limit_kb = self.domain_settings.get("USER_MODULE_SETTINGS", {}).get("SOGO_D_SIGNATURE_SIZE_LIMIT", 200)
        # Convert from KB to bytes (size_limit_kb is in kilobytes)
        return size_limit_kb * 1024 if size_limit_kb > 0 else 0

    def _validate_signatures_size(self, identities: List[Dict[str, Any]]) -> None:
        """Validate that all signatures in identities do not exceed the size limit (bytes).
        
        :param identities: List of identity dictionaries containing signatures
        :type identities: List[Dict[str, Any]]
        :raises RequestException: If any signature exceeds the size limit
        """
        size_limit = self._get_signature_size_limit()
        if size_limit <= 0:
            return  # No limit set

        for identity in identities:
            signatures = identity.get("signatures", {})
            if isinstance(signatures, dict):
                for _, signature_value in signatures.items():
                    if isinstance(signature_value, str) and len(signature_value.encode('utf-8')) > size_limit:
                        raise RequestException(
                            err.ERROR_SIGNATURE_SIZE_EXCEEDED.m,
                            err.ERROR_SIGNATURE_SIZE_EXCEEDED
                        )

    def _apply_identity_restrictions(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """Apply identity restrictions to a main account based on domain settings.
        
        This method filters and modifies identities in the account according to:
        - If identities are disabled: only return the default identity
        - If custom from is disabled: replace mail with user's mail
        - If custom name is disabled: replace name with user's cn
        - If custom reply-to is disabled: replace reply-to with user's mail
        
        :param account: The account data containing identities
        :type account: Dict[str, Any]
        :return: The account with restrictions applied
        :rtype: Dict[str, Any]
        """
        if "identities" not in account:
            return account

        identities = account.get("identities", [])

        # If identities are disabled, only keep the default identity
        if not self._is_identities_enabled():
            identities = [identity for identity in identities if identity.get("isDefault", False)]
            # If no default identity found, keep the first one
            if not identities and account.get("identities"):
                identities = [account["identities"][0]]

        # Apply field restrictions to all identities
        for identity in identities:
            if not self._is_custom_from_enabled():
                identity["mail"] = self.user.mail
            if not self._is_custom_name_enabled():
                identity["name"] = self.user.cn
            if not self._is_custom_reply_to_enabled():
                identity["reply-to"] = self.user.mail

        account["identities"] = identities
        return account

    def _get_user_conf(self, account_id: int) -> Dict[str, Any]:
        """
        Select and validate the configuration for a given account ID.
        """
        raise NotImplementedError("_get_user_conf is not implemented yet")

    def list_mailboxes(self) -> Tuple[Dict[str, Any], int]:
        """List all configured mailboxes.
        
        If external accounts are not allowed for this domain, only returns the main account.
        
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            list_accounts = self.module_user_profile.list_accounts(self.user)
            return create_api_base_response(list_accounts), 200
        except RequestException as ex:
            logger_api.error("Request exception in list_mailboxes for user %s: %s", self.user.uid, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def create_mailbox(self, account_data: dict) -> tuple[dict, int]:
        """Create a new mailbox (add external account).
        
        :param account_data: Validated account data from schema
        :type account_data: dict | None
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        # Check if external accounts are allowed for this domain
        if not self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
            return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN), err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.h
        
        try:
            account_response = self.module_user_profile.create_external_account(self.user.uid, account_data)
            return create_api_base_response(account_response), 201
        except RequestException as ex:
            logger_api.error("Request exception in create_mailbox for user %s: %s", self.user.uid, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_mailbox(self, account_id: str) -> tuple[dict, int]:
        """Get a specific account by its hash, or main account if account_id is "0".
        
        If account_id is not "0" and external accounts are not allowed, returns 403.
        
        :param account_id: The hash of the external account, or "0" for main account
        :type account_id: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        # If requesting an external account (not "0") and external accounts are not allowed
        if account_id != cs.DEFAULT_IDENTITY_KEY_VALUE and not self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
            return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN), err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.h
    
        try:
            account = self.module_user_profile.get_account_detail(self.user, account_id)
            return create_api_base_response(account), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status


    def update_mailbox(self, account_id: str, account_data: dict[str, Any]) -> tuple[dict, int]:
        """Update mailbox settings.
        
        :param account_id: The hash of the external account, or "0" for main account
        :type account_id: str
        :param account_data: Validated account data from schema
        :type account_data: dict | None
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """

        if account_id == cs.DEFAULT_IDENTITY_KEY_VALUE:
            try:
                updated_account = self.module_user_profile.update_main_account(self.user, account_data)
            except RequestException as ex:
                logger_api.error("Request exception in update_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
                return create_api_base_response(None, ex.error_code), ex.http_status
            return create_api_base_response(updated_account), 200
        else:
            if not self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
                return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN), err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.h
            try:
                updated_account = self.module_user_profile.update_external_account(self.user, account_id, account_data)
            except RequestException as ex:
                logger_api.error("Request exception in update_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
                return create_api_base_response(None, ex.error_code), ex.http_status
            return create_api_base_response(updated_account), 200
        


    def delete_mailbox(self, account_id: str) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Delete a mailbox (only external accounts).
        
        :param account_id: The hash of the external account
        :type account_id: str
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        try:
            # Check if trying to delete main account (account_id == "0")
            if account_id == cs.DEFAULT_IDENTITY_KEY_VALUE:
                raise RequestException(err.ERROR_MAIN_ACCOUNT_CANNOT_BE_DELETED.m, err.ERROR_MAIN_ACCOUNT_CANNOT_BE_DELETED)
            # Check if external accounts are allowed for this domain
            if not self._is_external_account_allowed():
                raise RequestException(
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.m,
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN
                )
            uid = self.user.uid
            self.module_user_profile.delete_external_account(uid, account_id)
            return "", 204
        except RequestException as ex:
            logger_api.error("Request exception in delete_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
        except BugException as ex:
            logger_api.error("Bug exception in delete_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def compose_email(self, account_id: int) -> Tuple[Dict[str, Any], int]:
        """Compose a new email from the specified mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        raise NotImplementedError("Compose email is not implemented yet")

    def get_mailbox_delegates(self, account_id: str) -> Tuple[Dict[str, Any], int]:
        """Get delegates for this mailbox.
        
        Note: Delegations are currently only supported for the main account (account_id="0").
        External accounts do not support delegations.
        
        :param account_id: The account identifier ("0" for main account)
        :type account_id: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            # Delegations are only supported for main account
            if account_id != cs.DEFAULT_IDENTITY_KEY_VALUE:
                raise RequestException(
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.m,
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN
                )
            
            uid = self.user.uid
            print(self.user)
            print(uid)
            delegations = self.module_user_profile.get_delegations_given(uid)
            return create_api_base_response(delegations), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_mailbox_delegates for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
        except BugException as ex:
            logger_api.error("Bug exception in get_mailbox_delegates for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status


    def create_mailbox_delegate(self, account_id: str, data: dict) -> Tuple[Dict[str, Any], int]:
        """Create a new delegate for this mailbox.
        
        Note: Delegations are currently only supported for the main account (account_id="0").
        External accounts do not support delegations.
        
        :param account_id: The account identifier ("0" for main account)
        :type account_id: str
        :param data: Delegate data containing 'email' field
        :type data: dict
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            # Delegations are only supported for main account
            if account_id != cs.DEFAULT_IDENTITY_KEY_VALUE:
                raise RequestException(
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.m,
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN
                )
            
            uid = self.user.uid
            delegate_email = data.get("email")
            
            if not delegate_email:
                raise RequestException(
                    err.ERROR_DELEGATION_INVALID_EMAIL.m,
                    err.ERROR_DELEGATION_INVALID_EMAIL
                )
            
            result = self.module_user_profile.add_delegation_given(uid, delegate_email)
            return create_api_base_response(result), 201
        except RequestException as ex:
            logger_api.error("Request exception in create_mailbox_delegate for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
        except BugException as ex:
            logger_api.error("Bug exception in create_mailbox_delegate for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status


    def purge_mailbox(self, account_id: int) -> Tuple[Union[str, Dict[str, Any]], int]:
        """Purge (all folders) from the specified mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (empty string or error dict, status code)
        :rtype: Tuple[Union[str, Dict[str, Any]], int]
        """
        raise NotImplementedError("Purge mailbox is not implemented yet")

