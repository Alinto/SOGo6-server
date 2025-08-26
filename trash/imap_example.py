import imaplib

imap = imaplib.IMAP4('192.168.21.81', 143)
#imap = imaplib.IMAP4_SSL('192.168.21.81', 993)
#imap = imaplib.IMAP4('localhost', 143)


imap.login("sogo-tests1@example.org", "sogo")

# Lister les boîtes
print("LIST:", imap.list())

# Sélection INBOX
typ, data = imap.select("INBOX")
print("SELECT INBOX:", typ, data)

# Statut boîte
print("STATUS INBOX:", imap.status("INBOX", "(MESSAGES UNSEEN RECENT)"))

# Chercher tous les mails
typ, data = imap.search(None, "ALL")
print("SEARCH ALL:", data)

# Chercher non lus
typ, data = imap.search(None, "UNSEEN")
print("SEARCH UNSEEN:", data)

imap.close()
imap.logout()
