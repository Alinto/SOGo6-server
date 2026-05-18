from __future__ import annotations
from typing import TYPE_CHECKING

from email.message import EmailMessage

from app.manager.outgoing.ClientOutgoing import ClientOutgoing
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.maths.crypto_utils import decrypt_password
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_mail_server

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.DomainSettings import MailSettingsObj


REGISTRY_MANAGER: dict[str, str] = {
    "smtp": "ClientSmtp",
    "sendmail": "ClientSendmail",
}


class ModuleMailOutgoing:
    """
    Module to handle outgoing mail operations using different client implementations
    (SMTP, Sendmail, ...).
    """

    def __init__(self, user: User, mail_settings: MailSettingsObj) -> None:
        self.user = user
        self.mail_settings = mail_settings

    def _get_outgoing_conf(self, account_id: str) -> dict:
        """Build the outgoing client configuration for the given account.

        For the main account (DEFAULT_IDENTITY_KEY_VALUE), use domain SMTP settings
        and the user's outgoing login. For external accounts, use the account's
        mail_outgoing config.

        :param account_id: Account identifier (DEFAULT_IDENTITY_KEY_VALUE or external id)
        :type account_id: str
        :return: Configuration dict with keys 'type', 'username', 'password', 'args'
        :rtype: dict
        :raises RequestException: If the external account is not found
        """
        conf: dict = {}

        if account_id == cs.DEFAULT_IDENTITY_KEY_VALUE:
            outgoing_type = self.mail_settings.SOGO_D_MAIL_OUTGOING_TYPE

            conf["username"] = self.user.login_mail_outgoing
            conf["password"] = self.user.password
            conf["type"] = outgoing_type

            if outgoing_type == "smtp":
                # Use master credentials if enabled
                if self.mail_settings.SOGO_D_SMTP_MASTER_ENABLED:
                    conf["username"] = self.mail_settings.SOGO_D_SMTP_MASTER_LOGIN
                    conf["password"] = decrypt_password(self.mail_settings.SOGO_D_SMTP_MASTER_PWD)
                    conf["authname"] = self.user.login_mail_outgoing
                else:
                    conf["authname"] = ""

                conf["args"] = {
                    "server": self.mail_settings.SOGO_D_SMTP_SERVER,
                    "port": self.mail_settings.SOGO_D_SMTP_PORT,
                    "encryption": self.mail_settings.SOGO_D_SMTP_ENCRYPTION,
                    "auth_mech": self.mail_settings.SOGO_D_SMTP_AUTH_MECH,
                }
            else:
                # sendmail and future mechanisms: no connection args needed
                conf["args"] = {}
                conf["authname"] = ""

        else:
            if not self.user.profile.external_accounts or account_id not in self.user.profile.external_accounts:
                raise RequestException(
                    err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m,
                    error=err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND
                )

            ext_account: dict = self.user.profile.external_accounts[account_id]
            outgoing_conf: dict = ext_account["mail_outgoing"]

            conf["type"] = outgoing_conf["type"]
            conf["username"] = outgoing_conf["username"]
            conf["password"] = decrypt_password(outgoing_conf["password"])
            conf["authname"] = ""
            conf["args"] = {
                "server": outgoing_conf["server"],
                "port": outgoing_conf["port"],
                "encryption": outgoing_conf["encryption"],
                "auth_mech": outgoing_conf["auth_mech"],
            }

        return conf

    def _open_client_for(self, account_id: str, do_login: bool = True) -> ClientOutgoing:
        """Open an outgoing mail client for the given account and optionally authenticate.

        :param account_id: Account identifier
        :type account_id: str
        :param do_login: Whether to authenticate after connecting, defaults to True
        :type do_login: bool
        :return: Connected (and optionally authenticated) outgoing client
        :rtype: ClientOutgoing
        """
        conf = self._get_outgoing_conf(account_id)

        client: ClientOutgoing = import_and_instantiate_manager(
            module_path="app.manager.outgoing",
            module_and_class_name=REGISTRY_MANAGER[conf["type"]],
            module_args=conf["args"],
        )
        client.connect()
        if do_login:
            client.login(conf["username"], conf["password"], conf.get("authname", ""))
        return client

    def send_mail(self, account_id: str, mail_data: dict) -> EmailMessage:
        """Send an email using the outgoing mail client associated with the given account.

        :param account_id: The account ID to use for sending the email.
        :type account_id: str
        :param mail_data: Dict containing all email fields (validated upstream).
        :type mail_data: dict
        :return: The built EmailMessage that was sent.
        :rtype: EmailMessage
        """
        message = EmailMessage()
        message["From"] = mail_data["from_addr"]
        message["To"] = ", ".join(mail_data["to"])
        message["Subject"] = mail_data["subject"]

        if cc := mail_data.get("cc"):
            message["Cc"] = ", ".join(cc)
        if bcc := mail_data.get("bcc"):
            message["Bcc"] = ", ".join(bcc)
        if return_receipt := mail_data.get("return_receipt"):
            message["Disposition-Notification-To"] = return_receipt

        message.set_content(mail_data["body"])

        for attachment in (mail_data.get("attachments") or []):
            try:
                message.add_attachment(
                    attachment["data"],
                    filename=attachment.get("filename", "file"),
                    maintype="application",
                    subtype="octet-stream",
                )
            except KeyError as exc:
                raise RequestException(
                    err.ERROR_MISSING_ACTION_DATA.m,
                    error=err.ERROR_MISSING_ACTION_DATA,
                ) from exc

        client = self._open_client_for(account_id)
        logger_mail_server.info(
            "Sending mail from account '%s' subject='%s'",
            account_id,
            mail_data["subject"],
        )
        client.send_mail(message)
        return message
