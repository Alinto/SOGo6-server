from __future__ import annotations
from typing import TYPE_CHECKING

from email.message import EmailMessage
from email.utils import make_msgid, formatdate, parseaddr

from app.manager.outgoing.ClientOutgoing import ClientOutgoing
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.maths.crypto_utils import decrypt_password
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_mail_server
from app.utils.strings import get_domain_from_mail

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

    def _get_outgoing_conf(self, account_id: str, is_system:bool = False) -> dict:
        """Build the outgoing client configuration for the given account.

        For the main account (DEFAULT_IDENTITY_KEY_VALUE), use domain SMTP settings
        and the user's outgoing login. For external accounts, use the account's
        mail_outgoing config.

        :param account_id: Account identifier (DEFAULT_IDENTITY_KEY_VALUE or external id)
        :type account_id: str
        :param is_system: True if the message is a system message (notificaiton, noreply...)
        :type is_system: bool
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
                if is_system and self.mail_settings.SOGO_D_SMTP_MASTER_ENABLED:
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

    def send_mail(self, account_id: str, mail_data: dict, extra_headers: dict | None = None) -> EmailMessage:
        """Send an email using the outgoing mail client associated with the given account.

        :param account_id: The account ID to use for sending the email.
        :type account_id: str
        :param mail_data: Dict containing all email fields (validated upstream).
        :type mail_data: dict
        :param extra_headers: Optional RFC 5322 headers to inject into the message
            (e.g. ``{"In-Reply-To": "...", "References": "..."}``). These are added
            after the standard headers so they can never overwrite ``From``, ``To``,
            ``Subject``, ``Message-ID`` or ``Date``.
        :type extra_headers: dict | None
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
        if mail_data.get("return_receipt", False):
            message["Disposition-Notification-To"] = message["From"]  # RFC 3798
            message["Return-Receipt-To"] = message["From"]             # RFC 3885

        # --- X-Priority header ---
        if priority := mail_data.get("priority"):
            message["X-Priority"] = str(priority)

        # --- Reply-To header ---
        if reply_to := mail_data.get("reply_to"):
            message["Reply-To"] = reply_to

        # --- Message-ID: generate once, never overwrite ---
        if "Message-ID" not in message:
            _, addr = parseaddr(mail_data.get("from_addr", ""))
            domain = get_domain_from_mail(addr)
            message["Message-ID"] = make_msgid(domain=domain)

        # --- Date: always reflect the actual send time ---
        if "Date" in message:
            del message["Date"]
        message["Date"] = formatdate(localtime=True)

        # --- Extra RFC 5322 headers ---
        if extra_headers:
            for header_name, header_value in extra_headers.items():
                if header_name not in message:
                    message[header_name] = header_value

        # --- Body: multipart/alternative if is_html is True, else text/plain only ---
        body_text = mail_data["body"]
        is_html = mail_data.get("is_html", True)
        
        if is_html:
            message.set_content(body_text, subtype="plain")
            message.add_alternative(body_text, subtype="html")
        else:
            message.set_content(body_text, subtype="plain")

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
