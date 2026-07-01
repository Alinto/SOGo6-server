"""
Tests unitaires pour ClientSmtp (Manager layer).
Ces tests utilisent des mock objects pour simuler les réponses SMTP.
"""
import pytest
import smtplib
from email.message import EmailMessage
from socket import timeout as sock_timeout, gaierror
from ssl import SSLError
from unittest import mock

from app.manager.outgoing.ClientSmtp import ClientSmtp
from app.utils.exceptions import RequestException, BugException
from app.utils import constants as cs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client(server="smtp.example.com", port=587,
                encryption=cs.SOCKET_ENC_PLAIN,
                auth_mech="plain") -> ClientSmtp:
    """Build a ClientSmtp with sensible defaults."""
    return ClientSmtp(server=server, port=port, encryption=encryption, auth_mech=auth_mech)


def connected_client(fake_conn) -> ClientSmtp:
    """Return a ClientSmtp that looks already connected + authenticated."""
    client = make_client()
    client.connection = fake_conn
    client.connected = True
    client.authenticated = True
    return client


# ---------------------------------------------------------------------------
# Fake SMTP connection
# ---------------------------------------------------------------------------

class FakeSMTPConnection:
    """Minimal fake that mimics smtplib.SMTP responses."""

    def __init__(self):
        self.debug_level = 0
        self.esmtp_features: dict = {}

        # Configurable failure flags
        self.ehlo_should_fail = False
        self.starttls_should_fail = False
        self.docmd_should_fail = False

        # Records of sent messages
        self.sent_messages: list = []

    def set_debuglevel(self, level: int) -> None:
        self.debug_level = level

    def ehlo(self) -> tuple:
        if self.ehlo_should_fail:
            raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
        return (250, b"smtp.example.com Hello")

    def starttls(self) -> tuple:
        if self.starttls_should_fail:
            raise smtplib.SMTPException("STARTTLS failed")
        return (220, b"Ready to start TLS")

    def docmd(self, cmd: str, args: str = "") -> tuple:
        if self.docmd_should_fail:
            raise smtplib.SMTPAuthenticationError(535, b"Authentication credentials invalid")
        return (235, b"2.7.0 Authentication successful")

    def send_message(self, message) -> dict:
        self.sent_messages.append(message)
        return {}

    def quit(self) -> tuple:
        return (221, b"Bye")


# ===========================================================================
# Tests: ClientSmtp.__init__
# ===========================================================================

class TestClientSmtpInit:
    def test_init_sets_all_attributes(self):
        client = make_client()
        assert client.server == "smtp.example.com"
        assert client.port == 587
        assert client.encryption == cs.SOCKET_ENC_PLAIN
        assert client.auth_mech == "plain"
        assert client.connection is None
        assert client.connected is False
        assert client.authenticated is False

    def test_init_implicit_tls(self):
        client = make_client(encryption=cs.SOCKET_ENC_IMPLICIT_TLS)
        assert client.encryption == cs.SOCKET_ENC_IMPLICIT_TLS

    def test_init_explicit_tls(self):
        client = make_client(encryption=cs.SOCKET_ENC_EXPLICIT_TLS)
        assert client.encryption == cs.SOCKET_ENC_EXPLICIT_TLS

    def test_init_auth_mech_none(self):
        client = make_client(auth_mech="None")
        assert client.auth_mech == "None"

    def test_init_auth_mech_xoauth2(self):
        client = make_client(auth_mech="xoauth2")
        assert client.auth_mech == "xoauth2"

    def test_init_auth_mech_oauthbearer(self):
        client = make_client(auth_mech="oauthbearer")
        assert client.auth_mech == "oauthbearer"

    def test_init_connection_is_none(self):
        client = make_client()
        assert client.connection is None


# ===========================================================================
# Tests: connect
# ===========================================================================

class TestConnect:
    def test_connect_plain_creates_smtp(self):
        client = make_client(encryption=cs.SOCKET_ENC_PLAIN)
        fake_conn = FakeSMTPConnection()
        with mock.patch("app.manager.outgoing.ClientSmtp.smtplib.SMTP", return_value=fake_conn):
            client.connect()
        assert client.connected is True
        assert client.connection is fake_conn

    def test_connect_explicit_tls_calls_starttls(self):
        client = make_client(encryption=cs.SOCKET_ENC_EXPLICIT_TLS)
        fake_conn = FakeSMTPConnection()
        with mock.patch("app.manager.outgoing.ClientSmtp.smtplib.SMTP", return_value=fake_conn):
            with mock.patch.object(fake_conn, "starttls", wraps=fake_conn.starttls) as mock_starttls:
                client.connect()
                mock_starttls.assert_called_once()
        assert client.connected is True

    def test_connect_implicit_tls_creates_smtp_ssl(self):
        client = make_client(encryption=cs.SOCKET_ENC_IMPLICIT_TLS)
        fake_conn = FakeSMTPConnection()
        with mock.patch("app.manager.outgoing.ClientSmtp.smtplib.SMTP_SSL", return_value=fake_conn):
            client.connect()
        assert client.connected is True
        assert client.connection is fake_conn

    def test_connect_unknown_encryption_raises_bug_exception(self):
        client = make_client(encryption="UNKNOWN_ENC")
        with pytest.raises(BugException):
            client.connect()

    def test_connect_calls_ehlo(self):
        client = make_client(encryption=cs.SOCKET_ENC_PLAIN)
        fake_conn = FakeSMTPConnection()
        with mock.patch("app.manager.outgoing.ClientSmtp.smtplib.SMTP", return_value=fake_conn):
            with mock.patch.object(fake_conn, "ehlo", wraps=fake_conn.ehlo) as mock_ehlo:
                client.connect()
                mock_ehlo.assert_called_once()

    def test_connect_smtp_connect_error_raises_request_exception(self):
        client = make_client()
        with mock.patch(
            "app.manager.outgoing.ClientSmtp.smtplib.SMTP",
            side_effect=smtplib.SMTPConnectError(421, b"Service unavailable"),
        ):
            with pytest.raises(RequestException):
                client.connect()

    def test_connect_server_disconnected_raises_request_exception(self):
        client = make_client()
        with mock.patch(
            "app.manager.outgoing.ClientSmtp.smtplib.SMTP",
            side_effect=smtplib.SMTPServerDisconnected("Connection unexpectedly closed"),
        ):
            with pytest.raises(RequestException):
                client.connect()

    def test_connect_gaierror_raises_request_exception(self):
        client = make_client()
        with mock.patch(
            "app.manager.outgoing.ClientSmtp.smtplib.SMTP",
            side_effect=gaierror("Name or service not known"),
        ):
            with pytest.raises(RequestException):
                client.connect()

    def test_connect_timeout_raises_request_exception(self):
        client = make_client()
        with mock.patch(
            "app.manager.outgoing.ClientSmtp.smtplib.SMTP",
            side_effect=sock_timeout("Connection timed out"),
        ):
            with pytest.raises(RequestException):
                client.connect()

    def test_connect_connection_refused_raises_request_exception(self):
        client = make_client()
        with mock.patch(
            "app.manager.outgoing.ClientSmtp.smtplib.SMTP",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            with pytest.raises(RequestException):
                client.connect()

    def test_connect_ssl_error_raises_request_exception(self):
        client = make_client(encryption=cs.SOCKET_ENC_IMPLICIT_TLS)
        with mock.patch(
            "app.manager.outgoing.ClientSmtp.smtplib.SMTP_SSL",
            side_effect=SSLError("SSL handshake failed"),
        ):
            with pytest.raises(RequestException):
                client.connect()

    def test_connect_generic_smtp_exception_raises_request_exception(self):
        client = make_client()
        with mock.patch(
            "app.manager.outgoing.ClientSmtp.smtplib.SMTP",
            side_effect=smtplib.SMTPException("Generic SMTP error"),
        ):
            with pytest.raises(RequestException):
                client.connect()

    def test_connect_sets_connected_true_on_success(self):
        client = make_client()
        fake_conn = FakeSMTPConnection()
        assert client.connected is False
        with mock.patch("app.manager.outgoing.ClientSmtp.smtplib.SMTP", return_value=fake_conn):
            client.connect()
        assert client.connected is True

    def test_connect_does_not_set_authenticated(self):
        """connect() alone must NOT set authenticated; that is login()'s job."""
        client = make_client()
        fake_conn = FakeSMTPConnection()
        with mock.patch("app.manager.outgoing.ClientSmtp.smtplib.SMTP", return_value=fake_conn):
            client.connect()
        assert client.authenticated is False


# ===========================================================================
# Tests: login
# ===========================================================================

class TestLogin:
    def test_login_no_connection_raises_bug_exception(self):
        client = make_client()
        client.connection = None
        with pytest.raises(BugException):
            client.login("user@example.com", "password")

    def test_login_auth_none_success(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="None")
        client.connection = fake_conn
        client.connected = True

        client.login("user@example.com", "password")

        assert client.authenticated is True

    def test_login_auth_none_does_not_call_docmd(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="None")
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "docmd", wraps=fake_conn.docmd) as mock_docmd:
            client.login("user@example.com", "password")
            mock_docmd.assert_not_called()

    def test_login_plain_success(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="plain")
        client.connection = fake_conn
        client.connected = True

        client.login("user@example.com", "password")

        assert client.authenticated is True

    def test_login_plain_calls_docmd_with_plain_keyword(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="plain")
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "docmd", wraps=fake_conn.docmd) as mock_docmd:
            client.login("user@example.com", "password")
            mock_docmd.assert_called_once()
            cmd, args = mock_docmd.call_args[0]
            assert cmd == "AUTH"
            assert "PLAIN" in args

    def test_login_plain_with_authname_uses_authname_as_authzid(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="plain")
        client.connection = fake_conn
        client.connected = True

        # Should not raise; authname is used as authzid in the PLAIN credentials
        client.login("user@example.com", "password", authname="admin@example.com")

        assert client.authenticated is True

    def test_login_xoauth2_success(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="xoauth2")
        client.connection = fake_conn
        client.connected = True

        client.login("user@example.com", "token_value")

        assert client.authenticated is True

    def test_login_xoauth2_calls_docmd_with_xoauth2_keyword(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="xoauth2")
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "docmd", wraps=fake_conn.docmd) as mock_docmd:
            client.login("user@example.com", "token")
            cmd, args = mock_docmd.call_args[0]
            assert cmd == "AUTH"
            assert "XOAUTH2" in args

    def test_login_oauthbearer_success(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="oauthbearer")
        client.connection = fake_conn
        client.connected = True

        client.login("user@example.com", "token_value")

        assert client.authenticated is True

    def test_login_oauthbearer_calls_docmd_with_oauthbearer_keyword(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="oauthbearer")
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "docmd", wraps=fake_conn.docmd) as mock_docmd:
            client.login("user@example.com", "token")
            cmd, args = mock_docmd.call_args[0]
            assert cmd == "AUTH"
            assert "OAUTHBEARER" in args

    def test_login_unknown_mech_raises_bug_exception(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="unknown_mech")
        client.connection = fake_conn
        client.connected = True

        with pytest.raises(BugException):
            client.login("user@example.com", "password")

    def test_login_unknown_mech_does_not_set_authenticated(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="unknown_mech")
        client.connection = fake_conn
        client.connected = True

        with pytest.raises(BugException):
            client.login("user@example.com", "password")

        assert client.authenticated is False

    def test_login_smtp_auth_error_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        fake_conn.docmd_should_fail = True
        client = make_client(auth_mech="plain")
        client.connection = fake_conn
        client.connected = True

        with pytest.raises(RequestException):
            client.login("user@example.com", "wrong_password")

    def test_login_smtp_response_error_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="plain")
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "docmd",
                               side_effect=smtplib.SMTPResponseException(500, b"Server error")):
            with pytest.raises(RequestException):
                client.login("user@example.com", "password")

    def test_login_smtp_generic_exception_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = make_client(auth_mech="plain")
        client.connection = fake_conn
        client.connected = True

        with mock.patch.object(fake_conn, "docmd",
                               side_effect=smtplib.SMTPException("Unexpected SMTP error")):
            with pytest.raises(RequestException):
                client.login("user@example.com", "password")

    def test_login_failure_does_not_set_authenticated(self):
        fake_conn = FakeSMTPConnection()
        fake_conn.docmd_should_fail = True
        client = make_client(auth_mech="plain")
        client.connection = fake_conn
        client.connected = True

        with pytest.raises(RequestException):
            client.login("user@example.com", "wrong_password")

        assert client.authenticated is False


# ===========================================================================
# Tests: send_mail
# ===========================================================================

def _make_message() -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Test subject"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg.set_content("Hello, world!")
    return msg


class TestSendMail:
    def test_send_mail_no_connection_raises_bug_exception(self):
        client = make_client()
        client.connection = None

        with pytest.raises(BugException):
            client.send_mail(_make_message())

    def test_send_mail_success(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)

        client.send_mail(_make_message())

        assert len(fake_conn.sent_messages) == 1

    def test_send_mail_passes_correct_message_object(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)
        msg = _make_message()

        client.send_mail(msg)

        assert fake_conn.sent_messages[0] is msg

    def test_send_mail_smtp_auth_error_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)

        with mock.patch.object(fake_conn, "send_message",
                               side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed")):
            with pytest.raises(RequestException):
                client.send_mail(_make_message())

    def test_send_mail_server_disconnected_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)

        with mock.patch.object(fake_conn, "send_message",
                               side_effect=smtplib.SMTPServerDisconnected("Server went away")):
            with pytest.raises(RequestException):
                client.send_mail(_make_message())

    def test_send_mail_recipients_refused_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)

        with mock.patch.object(
            fake_conn, "send_message",
            side_effect=smtplib.SMTPRecipientsRefused({"recipient@example.com": (550, b"User unknown")}),
        ):
            with pytest.raises(RequestException):
                client.send_mail(_make_message())

    def test_send_mail_sender_refused_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)

        with mock.patch.object(
            fake_conn, "send_message",
            side_effect=smtplib.SMTPSenderRefused(553, b"Sender refused", "sender@example.com"),
        ):
            with pytest.raises(RequestException):
                client.send_mail(_make_message())

    def test_send_mail_data_error_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)

        with mock.patch.object(fake_conn, "send_message",
                               side_effect=smtplib.SMTPDataError(550, b"Data error")):
            with pytest.raises(RequestException):
                client.send_mail(_make_message())

    def test_send_mail_response_error_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)

        with mock.patch.object(fake_conn, "send_message",
                               side_effect=smtplib.SMTPResponseException(500, b"Response error")):
            with pytest.raises(RequestException):
                client.send_mail(_make_message())

    def test_send_mail_generic_smtp_exception_raises_request_exception(self):
        fake_conn = FakeSMTPConnection()
        client = connected_client(fake_conn)

        with mock.patch.object(fake_conn, "send_message",
                               side_effect=smtplib.SMTPException("Generic SMTP error")):
            with pytest.raises(RequestException):
                client.send_mail(_make_message())
