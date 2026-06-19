from __future__ import annotations
from typing import TYPE_CHECKING


from app.config.settings.DomainSettings import UserModuleSettings, UserModuleSettingsObj, MailSettings, MailSettingsObj
from app.module.mail.ModuleMail import ModuleMail
from app.module.mail.ModuleMailOutgoing import ModuleMailOutgoing
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.exceptions import RequestException
from app.utils.api.ApiBaseResponse import create_api_base_response
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
        user_domain: dict
    ) -> None:
        self.process_setting = process_setting
        self.user = user
        self.user_module_settings = UserModuleSettingsObj(user_domain[UserModuleSettings.subparent])
        self.module_user_profile = ModuleUserProfile(process_setting, user_domain)
        self.mail_settings = MailSettingsObj(user_domain[MailSettings.subparent])
        self.mail_module = ModuleMail(user, self.mail_settings, process_setting)
        self.mail_outgoing_module = ModuleMailOutgoing(user, self.mail_settings)


    def save_draft(self, account_id: str, mail_data: dict, key: str | None = None, close: bool = False) -> tuple[dict, int]:
        """Save a mail as a draft in the account's Drafts folder.

        Delegates to ModuleMail which manages the tmp_draft table and the IMAP APPEND operation.
        The response data includes the tmp_draft key so the client can reference it in subsequent calls.
        If *close* is True, the tmp_draft row is deleted after saving (the IMAP draft is kept).

        :param account_id: The account identifier ("0" for main account, hash for external)
        :type account_id: str
        :param mail_data: Dict with draft fields (from_addr, to, subject, body, ...)
        :type mail_data: dict
        :param key: Optional tmp_draft key; if None a new tmp_draft entry is created
        :type key: str | None
        :param close: If True, delete the tmp_draft row after saving (keep the IMAP draft)
        :type close: bool
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        try:
            result = self.mail_module.save_draft(account_id, mail_data, key, close=close)
            return create_api_base_response(result)
        except RequestException as ex:
            logger_api.error("Request exception in save_draft for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)

    def send_mail(self, account_id: str, mail_data: dict, key: str | None = None) -> tuple[dict, int]:
        """Send an email from the specified account.

        :param account_id: The account identifier ("0" for main account, hash for external)
        :type account_id: str
        :param mail_data: Validated mail data from schema
        :type mail_data: dict
        :param draft_uid: Optional UID of the draft mail to delete after sending
        :type draft_uid: str | None
        :param key: Optional tmp_draft key; if provided, it is validated (existence, ownership, lock)
            and the entry is deleted after a successful send
        :type key: str | None
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        if key is not None:
            try:
                self.mail_module.validate_tmp_draft_key(key)
            except RequestException as ex:
                logger_api.error("Invalid tmp_draft key %s for user %s: %s", key, self.user.uid, str(ex))
                return create_api_base_response(None, ex.error)

            # Retrieve threading headers stored in the tmp_draft row
            extra_headers: dict = {}
            try:
                extra_headers = self.mail_module.get_headers_from_tmp_draft(key)
            except RequestException as ex:
                logger_api.warning("Failed to retrieve headers from tmp_draft key %s for user %s: %s", key, self.user.uid, str(ex))

            # Inject attachments stored in the IMAP draft into mail_data before sending
            try:
                draft_attachments = self.mail_module.get_attachments_from_tmp_draft(account_id, key)
                if draft_attachments:
                    existing = mail_data.get("attachments") or []
                    mail_data = dict(mail_data)
                    mail_data["attachments"] = existing + draft_attachments
            except RequestException as ex:
                logger_api.warning("Failed to retrieve attachments from tmp_draft key %s for user %s: %s", key, self.user.uid, str(ex))
        else:
            extra_headers = {}
        try:
            message = self.mail_outgoing_module.send_mail(account_id, mail_data, extra_headers=extra_headers or None)
        except RequestException as ex:
            logger_api.error("Request exception in send_mail for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error, error_msg=str(ex))

        try:
            self.mail_module.save_mail_to_folder(account_id, message, cs.MAIL_FOLDER_SENT)
        except RequestException as ex:
            logger_api.warning("Failed to save sent mail to Sent folder for user %s, account %s: %s", self.user.uid, account_id, str(ex))

        if key is not None:
            try:
                self.mail_module.delete_tmp_draft(key, account_id)
            except RequestException as ex:
                logger_api.warning("Failed to delete tmp_draft key %s for user %s: %s", key, self.user.uid, str(ex))

        return create_api_base_response(None)

    def delete_draft(self, account_id: str, key: str) -> tuple[dict, int]:
        """Delete the IMAP draft and its tmp_draft row.

        :param account_id: The account identifier.
        :type account_id: str
        :param key: The tmp_draft key (mandatory).
        :type key: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        try:
            self.mail_module.delete_draft_and_tmp(account_id, key)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("Request exception in delete_draft for user %s, account %s, key %s: %s", self.user.uid, account_id, key, str(ex))
            return create_api_base_response(None, ex.error)

    def list_current_drafts(self) -> tuple[dict, int]:
        """Return all tmp_draft entries owned by the current user.

        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        try:
            result = self.mail_module.list_current_drafts()
            return create_api_base_response(result)
        except RequestException as ex:
            logger_api.error("Request exception in list_current_drafts for user %s: %s", self.user.uid, str(ex))
            return create_api_base_response(None, ex.error)

    def upload_attachment(self, account_id: str, filename: str, content_type: str, file_data: bytes, key: str | None = None) -> tuple[dict, int]:
        """Add an attachment to the "mail in progress" draft.

        :param account_id: The account identifier
        :type account_id: str
        :param filename: The attachment filename
        :type filename: str
        :param content_type: The MIME content type (e.g. "application/pdf")
        :type content_type: str
        :param file_data: Raw bytes of the attachment
        :type file_data: bytes
        :param key: Optional tmp_draft key; if None a new tmp_draft entry is created
        :type key: str | None
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        try:
            result = self.mail_module.upload_attachment(account_id, filename, content_type, file_data, key)
            return create_api_base_response(result)
        except RequestException as ex:
            logger_api.error("Request exception in upload_attachment for user %s, account %s: %s", self.user.uid, account_id, str(ex))
            return create_api_base_response(None, ex.error)

    def delete_attachment(self, account_id: str, key: str, filename: str) -> tuple[dict, int]:
        """Remove an attachment from the IMAP draft linked to *key*.

        :param account_id: The account identifier.
        :type account_id: str
        :param key: The tmp_draft key.
        :type key: str
        :param filename: The filename of the attachment to remove.
        :type filename: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict, int]
        """
        try:
            self.mail_module.delete_attachment(account_id, key, filename)
            return create_api_base_response(None)
        except RequestException as ex:
            logger_api.error("Request exception in delete_attachment for user %s, account %s, key %s: %s", self.user.uid, account_id, key, str(ex))
            return create_api_base_response(None, ex.error)

    def download_draft_attachment(self, account_id: str, key: str, filename: str) -> tuple[bytes, str] | tuple[dict, int]:
        """Download a single attachment from the IMAP draft linked to *key*.

        :param account_id: The account identifier.
        :type account_id: str
        :param key: The tmp_draft key.
        :type key: str
        :param filename: The filename of the attachment to download.
        :type filename: str
        :return: A tuple of (raw bytes, content_type) on success, or (API error response dict, status code) on failure.
        :rtype: tuple[bytes, str] | tuple[dict, int]
        """
        try:
            return self.mail_module.download_draft_attachment(account_id, key, filename)
        except RequestException as ex:
            logger_api.error("Request exception in download_draft_attachment for user %s, account %s, key %s: %s", self.user.uid, account_id, key, str(ex))
            return create_api_base_response(None, ex.error)
