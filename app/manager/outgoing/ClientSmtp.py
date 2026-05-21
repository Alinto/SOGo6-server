from __future__ import annotations

import smtplib
from email.message import Message
from socket import timeout as sock_timeout, gaierror
from ssl import SSLError
import base64

from app.manager.outgoing.ClientOutgoing import ClientOutgoing
from app.utils.exceptions import BugException, RequestException
from app.utils.logger.logger import logger_mail_outgoing
from app.utils import errors as err
from app.utils import constants as cs


class ClientSmtp(ClientOutgoing):
    """
    SMTP client implementation using smtplib.
    """

    def __init__(self, server: str, port: int, encryption: str, auth_mech: str) -> None:
        """
        Initialize the SMTP client.

        :param server: SMTP server hostname or IP address.
        :param port: SMTP server port.
        :param encryption: Encryption mode, one of SOCKET_ENC_PLAIN, SOCKET_ENC_EXPLICIT_TLS or SOCKET_ENC_IMPLICIT_TLS.
        :param auth_mech: Authentication mechanism, one of 'None', 'plain' or 'xoauth2'.
        """
        super().__init__()
        self.server = server
        self.port = port
        self.encryption = encryption
        self.auth_mech = auth_mech
        self.connection: smtplib.SMTP | smtplib.SMTP_SSL | None = None

    def connect(self) -> None:
        """
        Open connection with the SMTP server according to the encryption setting.
        """
        try:
            if self.encryption == cs.SOCKET_ENC_PLAIN:
                self.connection = smtplib.SMTP(self.server, self.port)
            elif self.encryption == cs.SOCKET_ENC_EXPLICIT_TLS:
                self.connection = smtplib.SMTP(self.server, self.port)
                self.connection.starttls()
            elif self.encryption == cs.SOCKET_ENC_IMPLICIT_TLS:
                self.connection = smtplib.SMTP_SSL(self.server, self.port) # TODO check
            else:
                raise BugException(f"Unknown encryption given: {self.encryption}")

            if self.connection:
                self.connection.set_debuglevel(1) #TODO: Link that to a admin debug settings
                self.connection.ehlo() #TODO: retirer ça?
                logger_mail_outgoing.info(self.connection.esmtp_features)

            self.connected = True
            logger_mail_outgoing.info("Successfully connected to SMTP server %s:%d", self.server, self.port)

        except smtplib.SMTPConnectError as e:
            logger_mail_outgoing.error("SMTP connect error to %s:%d - %s", self.server, self.port, e)
            raise RequestException(str(e), err.ERROR_SMTP_CONNECT_ERROR) from e
        except smtplib.SMTPServerDisconnected as e:
            logger_mail_outgoing.error("SMTP server disconnected %s:%d - %s", self.server, self.port, e)
            raise RequestException(str(e), err.ERROR_SMTP_SERVER_DISCONNECTED) from e
        except (gaierror, sock_timeout, TimeoutError, ConnectionRefusedError, SSLError, smtplib.SMTPException) as e:
            logger_mail_outgoing.error("SMTP connection error to %s:%d - %s", self.server, self.port, e)
            raise RequestException(str(e), err.ERROR_SMTP_CONNECTION_FAILED) from e

    def login(self, username: str, password: str, authname: str = "") -> None:
        """Login to the SMTP server SOGO_D_SMTP_AUTH_MECH.

        :param username: The username (authorization identity) for authentication.
        :type username: str
        :param password: The password/token for authentication.
        :type password: str
        :param authname: Optional authentication identity used for 'auth' mechanism.
        :type authname: str
        :raises BugException: If the auth mechanism is unknown or the connection is not open.
        :raises RequestException: If login fails (message is the raw library error).
        """
        if self.connection is None:
            raise BugException("Cannot login: not connected to SMTP server", err.ERROR_SMTP_FAILED)

        logger_mail_outgoing.info("Logging in as %s using auth_mech=%s", username, self.auth_mech)

        try:
            if self.auth_mech == "None":
                # No authentication required
                pass

            elif self.auth_mech == "login":
                self.connection.login(username, password)

            elif self.auth_mech == "plain":
                authcid = authname if authname else username
                credentials = base64.b64encode(
                    f"{username}\x00{authcid}\x00{password}".encode()
                ).decode()
                self.connection.docmd("AUTH", f"PLAIN {credentials}")

            elif self.auth_mech == "xoauth2":
                auth_string = f"user={username}\x01auth=Bearer {password}\x01\x01"
                credentials = base64.b64encode(auth_string.encode()).decode()
                self.connection.docmd("AUTH", f"XOAUTH2 {credentials}")

            elif self.auth_mech == "oauthbearer":
                auth_string = f"n,a={username},\x01host={self.server}\x01port={self.port}\x01auth=Bearer {password}\x01\x01"
                credentials = base64.b64encode(auth_string.encode()).decode()
                self.connection.docmd("AUTH", f"OAUTHBEARER {credentials}")

            else:
                raise BugException(f"Unsupported SMTP authentication mechanism: {self.auth_mech}", err.ERROR_SMTP_UNKNWON_AUTH_MECH)

            self.authenticated = True
            logger_mail_outgoing.info("Successfully authenticated to SMTP server as %s", username)

        except smtplib.SMTPAuthenticationError as e:
            logger_mail_outgoing.error("SMTP authentication error for %s: %s", username, e)
            raise RequestException(str(e), err.ERROR_SMTP_UNAUTHORIZED) from e
        except smtplib.SMTPResponseException as e:
            logger_mail_outgoing.error("SMTP response error for %s: %s", username, e)
            raise RequestException(str(e), err.ERROR_SMTP_RESPONSE_ERROR) from e
        except smtplib.SMTPException as e:
            logger_mail_outgoing.error("SMTP login error for %s: %s", username, e)
            raise RequestException(str(e), err.ERROR_SMTP_FAILED) from e

    def send_mail(self, message: Message) -> None:
        """Send a mail using an email.message.Message object.

        :param message: The email message to send.
        :type message: email.message.Message
        """
        if self.connection is None:
            raise BugException("Cannot send mail: not connected to SMTP server", err.ERROR_SMTP_FAILED)
        try:
            self.connection.send_message(message)
        except smtplib.SMTPAuthenticationError as e:
            logger_mail_outgoing.error("SMTP authentication error while sending mail: %s", e)
            raise RequestException(str(e), err.ERROR_SMTP_UNAUTHORIZED) from e
        except smtplib.SMTPServerDisconnected as e:
            logger_mail_outgoing.error("SMTP server disconnected while sending mail: %s", e)
            raise RequestException(str(e), err.ERROR_SMTP_SERVER_DISCONNECTED) from e
        except smtplib.SMTPRecipientsRefused as e:
            logger_mail_outgoing.error("SMTP recipients refused while sending mail: %s", e)
            raise RequestException(str(e), err.ERROR_SMTP_RECIPIENTS_REFUSED) from e
        except smtplib.SMTPSenderRefused as e:
            logger_mail_outgoing.error("SMTP sender refused while sending mail: %s", e)
            raise RequestException(str(e), err.ERROR_SMTP_SENDER_REFUSED) from e
        except smtplib.SMTPDataError as e:
            logger_mail_outgoing.error("SMTP data error while sending mail: %s", e)
            raise RequestException(str(e), err.ERROR_SMTP_DATA_ERROR) from e
        except smtplib.SMTPResponseException as e:
            logger_mail_outgoing.error("SMTP response error while sending mail: %s", e)
            raise RequestException(str(e), err.ERROR_SMTP_RESPONSE_ERROR) from e
        except smtplib.SMTPException as e:
            logger_mail_outgoing.error("SMTP error while sending mail: %s", e)
            raise RequestException(str(e), err.ERROR_SMTP_FAILED) from e
