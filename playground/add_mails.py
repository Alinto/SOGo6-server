"""Remplit un dossier IMAP avec un grand nombre de mails de test (usage local uniquement)."""
import imaplib
import time
from email.message import EmailMessage
from email.utils import formatdate

HOST, PORT = "dovecot", 143
USER, PWD = "sogo-tests1@example.org", "sogo"
FOLDER = "INBOX/Trash"
NB_MAILS = 2000


def build_message(i: int, timestamp: float) -> bytes:
    msg = EmailMessage()
    msg["From"] = f"sender{i % 50}@example.com"
    msg["To"] = USER
    msg["Subject"] = f"Mail de test {i}"
    msg["Date"] = formatdate(timestamp, localtime=True)
    msg["Message-ID"] = f"<test-{i}-{int(time.time())}@local>"
    msg.set_content(f"Corps du message {i}")
    return msg.as_bytes()


def main() -> None:
    imap = imaplib.IMAP4(HOST, PORT)
    imap.login(USER, PWD)

    now = time.time()
    start = time.time()
    for i in range(1, NB_MAILS + 1):
        timestamp = now - i * 60  # dates étalées d'une minute
        status, data = imap.append(
            f'"{FOLDER}"', None, imaplib.Time2Internaldate(timestamp), build_message(i, timestamp)
        )
        if status != "OK":
            raise RuntimeError(f"Échec de l'ajout du mail {i}: {data}")
        if i % 100 == 0:
            print(f"{i}/{NB_MAILS} mails ajoutés ({time.time() - start:.1f}s)")

    status, data = imap.select(f'"{FOLDER}"', readonly=True)
    print(f"Terminé : {data[0].decode()} mails dans {FOLDER}")
    imap.logout()


if __name__ == "__main__":
    main()
