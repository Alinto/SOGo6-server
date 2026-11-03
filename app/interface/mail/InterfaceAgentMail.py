"""Worker-side interface for the mail module.

Mirrors ``InterfaceApiMailFolder`` but for the Agent: no Flask context, no HTTP
response formatting. Unlike calendar or contact, the mail server needs the user's
own credentials, so the User is rebuilt from its uid and password, exactly like the
Flask before_request does from the session, before instantiating ``ModuleMail``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.auth.User import User
from app.config.init_config import init_get_system_and_default_domain_settings, init_get_user_domain_settings
from app.config.settings.DomainSettings import MailSettings, MailSettingsObj
from app.interface.auth.InterfaceAuthUser import InterfaceAuthUser
from app.module.mail.ModuleMail import ModuleMail
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.maths.crypto_utils import decrypt_password

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


class InterfaceAgentMail:
    """Mail interface used by Agent tasks.

    Takes the identity the broker carries (uid, domain and encrypted password) and resolves
    the full ``User`` plus the user-scoped domain settings before instantiating ``ModuleMail``.
    """

    def __init__(self, process_setting: ProcessSetting, user_uid: str, domain: str, encrypted_password: str) -> None:
        self.user, user_domain_settings = self._load_user(process_setting, user_uid, domain, encrypted_password)
        self.module: ModuleMail = ModuleMail(
            self.user, MailSettingsObj(user_domain_settings[MailSettings.subparent]), process_setting=process_setting,
        )

    def empty_folder(self, account_id: str, folder_path: str) -> dict[str, int]:
        """Permanently delete every mail of a TRASH or JUNK folder.

        :param account_id: The account identifier ("0" for main, hash for external)
        :type account_id: str
        :param folder_path: The path of the folder to empty
        :type folder_path: str
        :return: ``{"mails_deleted": int}``
        :rtype: dict[str, int]
        """
        return self.module.empty_folder(account_id, folder_path)

    @staticmethod
    def _load_user(
        process_setting: ProcessSetting, user_uid: str, domain: str, encrypted_password: str,
    ) -> tuple[User, dict]:
        """Rehydrate a User and its domain settings. Same path as the Flask before_request.

        :raises RequestException: ERROR_USER_CREDS_NOT_VALID if the credentials are no longer valid.
        """
        system_settings, default_domain_settings = init_get_system_and_default_domain_settings()
        user: User = User(user_uid, decrypt_password(encrypted_password), domain=domain)
        user_domain_settings: dict = init_get_user_domain_settings(user, default_domain_settings)
        inter: InterfaceAuthUser = InterfaceAuthUser(process_setting, system_settings, user_domain_settings, user=user)
        creds_ok, user = inter.check_user_and_fill_info(user)
        if not creds_ok:
            raise RequestException(error=err.ERROR_USER_CREDS_NOT_VALID)
        return user, user_domain_settings
