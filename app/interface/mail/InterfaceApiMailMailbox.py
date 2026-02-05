from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, List, Union, Tuple, Optional

from flask import request

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
        self.user_domain = user_domain
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

    def create_mailbox(self, account_data: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], int]:
        """Create a new mailbox (add external account).
        
        :param account_data: Validated account data from schema
        :type account_data: dict | None
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            # Check if external accounts are allowed for this domain
            if not self._is_external_account_allowed():
                raise RequestException(
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.m,
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN
                )

            uid = self.user.uid
            if account_data is None:
                account_data = {}
            account_response = self.module_user_profile.create_external_account(uid, account_data)
            return create_api_base_response(account_response), 201
        except RequestException as ex:
            logger_api.error("Request exception in create_mailbox for user %s: %s", self.user.uid, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
        except BugException as ex:
            logger_api.error("Bug exception in create_mailbox for user %s: %s", self.user.uid, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def get_mailbox(self, account_id: str) -> Tuple[Dict[str, Any], int]:
        """Get a specific account by its hash, or main account if account_id is "0".
        
        If account_id is not "0" and external accounts are not allowed, returns 403.
        
        :param account_id: The hash of the external account, or "0" for main account
        :type account_id: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            # If requesting an external account (not "0") and external accounts are not allowed
            if account_id != cs.DEFAULT_IDENTITY_KEY_VALUE and not self._is_external_account_allowed():
                raise RequestException(
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.m,
                    err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN
                )
            uid = self.user.uid
            account = self.module_user_profile.get_account_detail(uid, account_id)

            # Apply identity restrictions to main account (id == "0")
            if account_id == cs.DEFAULT_IDENTITY_KEY_VALUE:
                self._apply_identity_restrictions(account)

            return create_api_base_response(account), 200
        except RequestException as ex:
            logger_api.error("Request exception in get_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
        except BugException as ex:
            logger_api.error("Bug exception in get_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

    def update_mailbox(self, account_id: str, account_data: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], int]:
        """Update mailbox settings.
        
        :param account_id: The hash of the external account, or "0" for main account
        :type account_id: str
        :param account_data: Validated account data from schema
        :type account_data: dict | None
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            uid = self.user.uid

            # If account_data is not provided (backward compatibility), get it from request
            if account_data is None:
                account_data = request.get_json()

            if not account_data or not isinstance(account_data, dict):
                return create_api_base_response(None, err.ERROR_API_NOT_JSON), 400

            # Check if updating main account (account_id == "0") or external account
            if account_id == cs.DEFAULT_IDENTITY_KEY_VALUE:
                if not self._is_identities_enabled():
                    if len(account_data.get("identities", [])) > 1:
                        raise RequestException(
                            err.ERROR_IDENTITIES_FORBIDDEN.m,
                            err.ERROR_IDENTITIES_FORBIDDEN
                        )
                    #only one identity
                    identity = account_data.get("identities", [])[0]
                    if not self._is_custom_from_enabled():
                    #mail in identities has to be the same as mail in user object
                        if identity.get("mail", "").lower() != self.user.mail.lower():
                            raise RequestException(
                                err.ERROR_IDENTITIES_CUSTOM_FROM_FORBIDDEN.m,
                                err.ERROR_IDENTITIES_CUSTOM_FROM_FORBIDDEN
                            )
                    if not self._is_custom_name_enabled():
                    # name in identity has to be the same as cn in user object
                        if identity.get("name", "") != self.user.cn:
                            raise RequestException(
                                err.ERROR_IDENTITIES_CUSTOM_NAME_FORBIDDEN.m,
                                err.ERROR_IDENTITIES_CUSTOM_NAME_FORBIDDEN
                            )
                    if not self._is_custom_reply_to_enabled():
                    # reply-to in identity has to be the same as mail in user object
                        if "reply-to" in identity and identity.get("reply-to", "").lower() != self.user.mail.lower():
                            raise RequestException(
                                err.ERROR_IDENTITIES_CUSTOM_REPLY_TO_FORBIDDEN.m,
                                err.ERROR_IDENTITIES_CUSTOM_REPLY_TO_FORBIDDEN
                            )

                updated_account = self.module_user_profile.update_main_account(uid, account_data)
                return create_api_base_response(updated_account), 200
            else:
                # Check if external accounts are allowed for this domain
                if not self._is_external_account_allowed():
                    raise RequestException(
                        err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN.m,
                        err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN
                    )
                updated_account = self.module_user_profile.update_external_account(uid, account_id, account_data)
                return create_api_base_response(updated_account), 200
        except RequestException as ex:
            logger_api.error("Request exception in update_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status
        except BugException as ex:
            logger_api.error("Bug exception in update_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error_code), ex.http_status

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
        # try:
        #     conf = self._get_user_conf(account_id)
        #     module = ModuleMail(user_conf=conf)
        #     email_data = module.compose_email()
        #     return create_api_base_response(email_data), 200
        # except ValidationError as ex:
        #     logger_api.error("Validation error in compose_email: %s", ex.messages)
        #     return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        # except RequestException as ex:
        #     logger_api.error("Request exception in compose_email: %s", str(ex))
        #     return create_api_base_response(None, ex.error_code), ex.http_status

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
        # try:
        #     conf = self._get_user_conf(account_id)
        #     module = ModuleMail(user_conf=conf)
        #     module.purge_mailbox()
        #     return "", 204
        # except ValidationError as ex:
        #     logger_api.error("Validation error in purge_mailbox: %s", ex.messages)
        #     return create_api_base_response(None, err.ERROR_VALIDATION_ERROR), 400
        # except RequestException as ex:
        #     logger_api.error("Request exception in purge_mailbox: %s", str(ex))
        #     return create_api_base_response(None, ex.error_code), ex.http_status
