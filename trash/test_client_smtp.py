"""
Manual test script for ClientSmtp.
Usage: python trash/test_client_smtp.py
"""
import sys
import os

# Make sure the workspace root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from email.mime.text import MIMEText

from app.manager.outgoing.ClientSmtp import ClientSmtp
from app.utils import constants as cs

SERVER = "postfix"
PORT = 25
#PORT_SSL = 10125   # TODO ??
USERNAME = "sogo-tests1@example.org"
PASSWORD = "sogo"
# For 'auth' mechanism: proxy authname
AUTHNAME = ""
# A fake Bearer token to use for OAuth tests (will fail auth but tests the code path)
OAUTH_TOKEN = "fake-bearer-token"


def test_connect(encryption: str, auth_mech: str = "None", port: int = PORT) -> ClientSmtp | None:
    print(f"\n------------- Testing connect() with encryption={encryption!r}, port={port} --------------")
    client = ClientSmtp(SERVER, port, encryption, auth_mech)
    try:
        client.connect()
        print(f"  connected={client.connected}")
        return client
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def test_send_mail(client: ClientSmtp, from_addr: str, to_addr: str) -> bool:
    print(f"\n--------------- Testing send_mail() from={from_addr!r} to={to_addr!r} ------------------")
    msg = MIMEText("This is a test email sent by test_client_smtp.py")
    msg["Subject"] = "ClientSmtp send_mail test v2"
    msg["From"] = from_addr
    msg["To"] = to_addr
    try:
        client.send_mail(msg)
        print("  send_mail OK")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def test_login(client: ClientSmtp, username: str, password: str, authname: str = "") -> bool:
    print(f"\n--------------- Testing login() with auth_mech={client.auth_mech!r}, username={username!r} ------------------")
    try:
        client.login(username, password, authname)
        print(f"  authenticated={client.authenticated}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


if __name__ == "__main__":
    # print("============================")
    # print("  PLAIN CONNECTION TESTS")
    # print("============================")

    # # Test plain connection, no auth (auth_mech="None")
    # print("\n=============1===============")
    # c = test_connect(cs.SOCKET_ENC_PLAIN, auth_mech="None")
    # if c:
    #     test_login(c, USERNAME, PASSWORD)

    # # Test plain connection + plain
    # print("\n=============2===============")
    # c = test_connect(cs.SOCKET_ENC_PLAIN, auth_mech="plain")
    # if c:
    #     test_login(c, USERNAME, PASSWORD)

    # # Test plain connection + auth
    # print("\n=============3===============")
    # c = test_connect(cs.SOCKET_ENC_PLAIN, auth_mech="auth")
    # if c:
    #     test_login(c, USERNAME, PASSWORD, authname=AUTHNAME)

    # # Test plain connection + auth mechanism with authname
    # print("\n=============4===============")
    # c = test_connect(cs.SOCKET_ENC_PLAIN, auth_mech="auth")
    # if c:
    #     test_login(c, USERNAME, PASSWORD, authname="blabalbla??@snapshot.alinto.org")

    # # Test plain connection + xoauth2 auth
    # print("\n=============5===============")
    # c = test_connect(cs.SOCKET_ENC_PLAIN, auth_mech="xoauth2")
    # if c:
    #     test_login(c, USERNAME, OAUTH_TOKEN)

    # # Test plain connection + oauthbearer auth
    # print("\n=============6===============")
    # c = test_connect(cs.SOCKET_ENC_PLAIN, auth_mech="oauthbearer")
    # if c:
    #     test_login(c, USERNAME, OAUTH_TOKEN)

    # # Test plain connection + unknown auth mech (should raise BugException)
    # print("\n=============7===============")
    # c = test_connect(cs.SOCKET_ENC_PLAIN, auth_mech="unknown_mech")
    # if c:
    #     test_login(c, USERNAME, PASSWORD)

    # print("\n============================")
    # print("  STARTTLS CONNECTION TESTS")
    # print("============================")

    # # Test STARTTLS + no auth
    # print("\n=============8===============")
    # c = test_connect(cs.SOCKET_ENC_EXPLICIT_TLS, auth_mech="None")
    # if c:
    #     test_login(c, USERNAME, PASSWORD)

    # # Test STARTTLS + plain auth
    # print("\n=============9===============")
    # c = test_connect(cs.SOCKET_ENC_EXPLICIT_TLS, auth_mech="plain")
    # if c:
    #     test_login(c, USERNAME, PASSWORD)

    # # Test STARTTLS + auth mechanism
    # print("\n=============10===============")
    # c = test_connect(cs.SOCKET_ENC_EXPLICIT_TLS, auth_mech="auth")
    # if c:
    #     test_login(c, USERNAME, PASSWORD, authname=AUTHNAME)

    # # Test STARTTLS + xoauth2
    # print("\n=============11===============")
    # c = test_connect(cs.SOCKET_ENC_EXPLICIT_TLS, auth_mech="xoauth2")
    # if c:
    #     test_login(c, USERNAME, OAUTH_TOKEN)

    # # Test STARTTLS + oauthbearer
    # print("\n=============12===============")
    # c = test_connect(cs.SOCKET_ENC_EXPLICIT_TLS, auth_mech="oauthbearer")
    # if c:
    #     test_login(c, USERNAME, OAUTH_TOKEN)

    print("\n============================")
    print("  SEND MAIL TESTS")
    print("============================")

    # Test send_mail after plain connection + plain auth
    print("\n=============13===============")
    c = test_connect(cs.SOCKET_ENC_PLAIN)
    if c and test_login(c, USERNAME, PASSWORD):
        test_send_mail(c, from_addr=USERNAME, to_addr=USERNAME)

    # # Test send_mail after STARTTLS + plain auth
    # print("\n=============14===============")
    # c = test_connect(cs.SOCKET_ENC_EXPLICIT_TLS, auth_mech="plain")
    # if c and test_login(c, USERNAME, PASSWORD):
    #     test_send_mail(c, USERNAME, USERNAME)

    # # Test send_mail without being connected (should raise BugException)
    # print("\n=============15===============")
    # print("\n--------------- Testing send_mail() without connection (expect BugException) ------------------")
    # disconnected = ClientSmtp(SERVER, PORT, cs.SOCKET_ENC_PLAIN, "plain")
    # test_send_mail(disconnected, USERNAME, USERNAME)





    # print("\n============================")
    # print("  IMPLICIT TLS CONNECTION TESTS")
    # print("============================")

    # # Test implicit TLS + no auth
    # c = test_connect(cs.SOCKET_ENC_IMPLICIT_TLS, auth_mech="None", port=PORT_SSL)
    # if c:
    #     test_login(c, USERNAME, PASSWORD)

    # # Test implicit TLS + plain auth
    # c = test_connect(cs.SOCKET_ENC_IMPLICIT_TLS, auth_mech="plain", port=PORT_SSL)
    # if c:
    #     test_login(c, USERNAME, PASSWORD)

    # # Test implicit TLS + auth mechanism
    # c = test_connect(cs.SOCKET_ENC_IMPLICIT_TLS, auth_mech="auth", port=PORT_SSL)
    # if c:
    #     test_login(c, USERNAME, PASSWORD, authname=AUTHNAME)

    # # Test implicit TLS + xoauth2
    # c = test_connect(cs.SOCKET_ENC_IMPLICIT_TLS, auth_mech="xoauth2", port=PORT_SSL)
    # if c:
    #     test_login(c, USERNAME, OAUTH_TOKEN)

    # # Test implicit TLS + oauthbearer
    # c = test_connect(cs.SOCKET_ENC_IMPLICIT_TLS, auth_mech="oauthbearer", port=PORT_SSL)
    # if c:
    #     test_login(c, USERNAME, OAUTH_TOKEN)
