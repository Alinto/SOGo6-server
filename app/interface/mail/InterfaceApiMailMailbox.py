from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, Union, Tuple
from http import HTTPStatus

from flask import request

from app.config.settings.DomainSettings import UserModuleSettings, UserModuleSettingsObj, MailSettings, MailSettingsObj
from app.module.mail.ModuleMail import ModuleMail
from app.module.mail.ModuleMailOutgoing import ModuleMailOutgoing
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
        self.mail_settings = MailSettingsObj(user_domain[MailSettings.subparent])
        self.mail_module = ModuleMail(user, self.mail_settings)
        self.mail_outgoing_module = ModuleMailOutgoing(user, self.mail_settings)

    def list_mailboxes(self) -> Tuple[Dict[str, Any], int]:
        """List all configured mailboxes.
        
        If external accounts are not allowed for this domain, only returns the main account.
        Enriches each account with quota information retrieved from the mail server.
        
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        try:
            list_accounts = self.module_user_profile.list_accounts(self.user)
        except RequestException as ex:
            logger_api.error("Request exception in list_mailboxes for user %s: %s", self.user.uid, str(ex))
            return create_api_base_response(None, ex.error)

        for account in list_accounts:
            account["invalid"] = False
            try:
                quota = self.mail_module.get_mailbox_quota(account["id"])
            except RequestException as ex:
                logger_api.error("Request exception in list_mailboxes (get_mailbox_quota) for user %s, account %s: %s", self.user.uid, account["id"], str(ex))
                account["invalid"] = True
                continue
            if quota is not None:
                account["quota"] = quota

        return create_api_base_response(list_accounts)

    def create_mailbox(self, account_data: dict) -> tuple[dict, int]:
        """Create a new mailbox (add external account).
        
        :param account_data: Validated account data from schema
        :type account_data: dict | None
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        # Check if external accounts are allowed for this domain
        if not self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
            return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN)

        try:
            account_response = self.module_user_profile.create_external_account(self.user.uid, account_data)
            return create_api_base_response(account_response, code=HTTPStatus.CREATED)
        except RequestException as ex:
            logger_api.error("Request exception in create_mailbox for user %s: %s", self.user.uid, str(ex))
            return create_api_base_response(None, ex.error)

    def get_mailbox(self, account_id: str) -> tuple[dict, int]:
        """Get a specific account by its hash, or main account if account_id is "0".
        
        If account_id is not "0" and external accounts are not allowed, returns 403.
        Enriches the account data with quota information retrieved from the mail server.
        
        :param account_id: The hash of the external account, or "0" for main account
        :type account_id: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        # If requesting an external account (not "0") and external accounts are not allowed
        if account_id != cs.DEFAULT_IDENTITY_KEY_VALUE and not self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
            return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN)

        try:
            account = self.module_user_profile.get_account_detail(self.user, account_id)
        except RequestException as ex:
            logger_api.error("Request exception in get_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)

        try:
            quota = self.mail_module.get_mailbox_quota(account_id)
        except RequestException as ex:
            logger_api.error("Request exception in get_mailbox (get_mailbox_quota) for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)
        if quota is not None:
            account["quota"] = quota

        return create_api_base_response(account)


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
                return create_api_base_response(None, ex.error)
            return create_api_base_response(updated_account)
        else:
            if not self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
                return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN)
            try:
                updated_account = self.module_user_profile.update_external_account(self.user, account_id, account_data)
            except RequestException as ex:
                logger_api.error("Request exception in update_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
                return create_api_base_response(None, ex.error)
            return create_api_base_response(updated_account)


    def delete_mailbox(self, account_id: str) -> tuple[str|dict, int]:
        """Delete a mailbox (only external accounts).
        
        :param account_id: The hash of the external account
        :type account_id: str
        :return: A tuple of (empty string or error dict, status code)
        :rtype: tuple[str|dict, int]
        """

        # Check if trying to delete main account (account_id == "0")
        if account_id == cs.DEFAULT_IDENTITY_KEY_VALUE:
            return create_api_base_response(error = err.ERROR_MAIN_ACCOUNT_CANNOT_BE_DELETED)

        # Check if user can use external account
        if not self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
            return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN)

        try:
            self.module_user_profile.delete_external_account(self.user, account_id)
            return "", HTTPStatus.NO_CONTENT
        except RequestException as ex:
            logger_api.error("Request exception in delete_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)


    def compose_email(self, account_id: int) ->  tuple[dict, int]:
        """Compose a new email from the specified mailbox.
        
        :param account_id: The account identifier
        :type account_id: int
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        raise NotImplementedError("Compose email is not implemented yet")


    def get_mailbox_delegates(self, account_id: str) ->  tuple[dict, int]:
        """Get delegates for this mailbox.
        
        Note: Delegations are currently only supported for the main account (account_id="0").
        External accounts do not support delegations.
        
        :param account_id: The account identifier ("0" for main account)
        :type account_id: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        if account_id != cs.DEFAULT_IDENTITY_KEY_VALUE:
            return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN)
        try:
            delegations = self.module_user_profile.get_delegations_given(self.user)
            return create_api_base_response(delegations)
        except RequestException as ex:
            logger_api.error("Request exception in get_mailbox_delegates for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)


    def create_mailbox_delegate(self, account_id: str, data: dict) ->  tuple[dict, int]:
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
        if account_id != cs.DEFAULT_IDENTITY_KEY_VALUE:
            return create_api_base_response(error = err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN)
        try:
            delegate_email = data["email"]
            result = self.module_user_profile.add_delegation_given(self.user, delegate_email)
            return create_api_base_response(result, code=HTTPStatus.CREATED)
        except RequestException as ex:
            logger_api.error("Request exception in create_mailbox_delegate for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)


    def purge_mailbox(self, account_id: str, purge_data: dict[str, Any]) -> tuple[dict, int]:
        """Purge all folders from the specified mailbox.

        Iterates over every folder in the account and purges mails
        (optionally before a given date, optionally permanently).

        :param account_id: The account identifier ("0" for main account, hash for external)
        :type account_id: str
        :param purge_data: dictionary containing purge options:
            - permanently_delete (bool): Expunge after marking as deleted
            - date (str): Delete mails before this date (YYYY-MM-DD format)
        :type purge_data: dict[str, Any]
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        # If requesting an external account (not "0") and external accounts are not allowed
        if account_id != cs.DEFAULT_IDENTITY_KEY_VALUE and not self.user_module_settings.SOGO_D_ALLOW_EXT_MAIL_ACCOUNT:
            return create_api_base_response(error=err.ERROR_EXTERNAL_ACCOUNT_FORBIDDEN)

        try:
            result = self.mail_module.purge_all_folders(account_id, purge_data)
            return create_api_base_response(result)
        except RequestException as ex:
            logger_api.error("Request exception in purge_mailbox for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)
        raise NotImplementedError("Purge mailbox is not implemented yet")


    def save_draft(self, account_id: str, mail_data: dict, uid: str | None = None) -> tuple[dict, int]:
        """Save a mail as a draft in the account's Drafts folder.

        If uid is provided and the draft already exists, it is replaced.
        If uid is absent or the draft is not found, a new draft is created.

        :param account_id: The account identifier ("0" for main account, hash for external)
        :type account_id: str
        :param mail_data: Dict with draft fields (from_addr, to, subject, body, ...)
        :type mail_data: dict
        :param uid: Optional UID of an existing draft to overwrite
        :type uid: str | None
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        try:
            result = self.mail_module.save_draft(account_id, mail_data, uid)
            return create_api_base_response(result)
        except RequestException as ex:
            logger_api.error("Request exception in save_draft for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)

    def send_mail(self, account_id: str, mail_data: dict, draft_uid: str | None = None) -> tuple[dict, int]:
        """Send an email from the specified account.

        :param account_id: The account identifier ("0" for main account, hash for external)
        :type account_id: str
        :param mail_data: Validated mail data from schema
        :type mail_data: dict
        :param draft_uid: Optional UID of the draft mail to delete after sending
        :type draft_uid: str | None
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        try:
            message = self.mail_outgoing_module.send_mail(account_id, mail_data)
        except RequestException as ex:
            logger_api.error("Request exception in send_mail for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error, error_msg=str(ex))

        try:
            self.mail_module.save_mail_to_folder(account_id, message, cs.MAIL_FOLDER_SENT)
        except RequestException as ex:
            logger_api.warning("Failed to save sent mail to Sent folder for user %s, account %s: %s", self.user.uid, account_id, str(ex))

        if draft_uid is not None:
            try:
                self.mail_module.delete_draft_mail(account_id, draft_uid)
            except RequestException as ex:
                logger_api.warning("Failed to delete draft mail uid %s for user %s, account %s: %s", draft_uid, self.user.uid, account_id, str(ex))

        return create_api_base_response(None)

