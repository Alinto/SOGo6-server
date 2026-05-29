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


class InterfaceApiMailSend:
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
