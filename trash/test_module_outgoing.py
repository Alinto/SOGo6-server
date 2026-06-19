"""
Manual test script for ModuleMailOutgoing.
Usage: python trash/test_module_outgoing.py
"""
import sys
import os

# Make sure the workspace root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock

from app.module.mail.ModuleMailOutgoing import ModuleMailOutgoing
from app.utils import constants as cs


SERVER   = "192.168.69.34"
PORT     = 10125
USERNAME = "tkeriven@snapshot.alinto.org"
PASSWORD = "Banane2!"

FROM_ADDR = USERNAME
TO_ADDR   = USERNAME
SUBJECT   = "ModuleMailOutgoing test"
BODY      = "This is a test email sent by test_module_outgoing.py"


def make_fake_user(username: str, password: str) -> MagicMock:
    user = MagicMock()
    user.login_mail_outgoing = username
    user.password = password
    return user



def make_fake_mail_settings(
    server: str,
    port: int,
    encryption: str = cs.SOCKET_ENC_PLAIN,
    auth_mech: str = "plain",
    master_enabled: bool = False,
) -> MagicMock:
    settings = MagicMock()
    settings.SOGO_D_MAIL_OUTGOING_TYPE = "smtp"
    settings.SOGO_D_SMTP_SERVER        = server
    settings.SOGO_D_SMTP_PORT          = port
    settings.SOGO_D_SMTP_ENCRYPTION    = encryption
    settings.SOGO_D_SMTP_AUTH_MECH     = auth_mech
    settings.SOGO_D_SMTP_MASTER_ENABLED = master_enabled
    return settings



def test_send_mail_simple() -> None:

    print(f"\n--- plain connection + plain auth, send to self ({TO_ADDR}) ---")

    user          = make_fake_user(USERNAME, PASSWORD)
    mail_settings = make_fake_mail_settings(SERVER, PORT, encryption=cs.SOCKET_ENC_PLAIN, auth_mech="plain")

    module = ModuleMailOutgoing(user, mail_settings)

    try:
        module.send_mail(
            account_id=cs.DEFAULT_IDENTITY_KEY_VALUE,
            mail_data={
                "from_addr": FROM_ADDR,
                "to": [TO_ADDR],
                "subject": SUBJECT,
                "body": BODY,
            },
        )
        print("  send_mail OK")
    except Exception as e:
        print(f"  FAILED: {e}")



if __name__ == "__main__":
    test_send_mail_simple()
