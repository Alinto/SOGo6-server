import imaplib
import re
from ast import literal_eval

username = "sogo-tests1@example.org"
password = "sogo"

# Prepare the PLAIN authentication string
auth_string = f"\0{username}\0{password}"


# #imap = imaplib.IMAP4('www.google.com', 81)
# imap = imaplib.IMAP4_SSL('192.168.21.81', 993)
print("hey")
imaplib.Debug = 4
print("hey")
imap = imaplib.IMAP4('dovecot', 143)
# imap = imaplib.IMAP4_SSL('dovecot', 993)


m = imap.login("sogo-tests1@example.org", "sogo")
print(m)

# imap.getquotaroot("INBOX")

m = imap.select("Drafts")
print(m)


# # # m = imap.fetch("1", "(BODYSTRUCTURE FLAGS UID)")
# m = imap.fetch("1:*", "(BODY.PEEK[HEADER] BODYSTRUCTURE FLAGS UID RFC822.SIZE)")
# # # m = imap.response('CAPABILITY')
# print(m)


# m = imap.namespace()
# print(m)

# print(m)
# def _extract_namespace(namespace_str:str, is_default:bool = False):
#     """
#     A imap namespace response is either 'NIL' or
#     '(("prefix1" "delimiter1" "extra_param_optionnal")("prefix2" "delimiter2"))
#     """
#     if namespace_str == "NIL":
#         return None
#     ##Removing the first '((' and last '))', then split ')('
#     namespace_list = namespace_str[2:-2].split(")(")
#     for idx, namespace in enumerate(namespace_list):
#         _, prefix, _, delimiter, *_ = namespace.split('"')
#         print(f"pref: {prefix}")
#         print(f"del: {delimiter}")

# # for idx, namespaces in enumerate('(("" "/")) NIL (("Public Folders/" "/"))'.split(" ")):
# #     print(namespaces)
# #     _extract_namespace(namespaces)


# #s = '(("" "/")) NIL (("Public Folders/" "/"))'
# #s = '(("" "/")) (("~" "/")) (("#shared/" "/")("#public/" "/")("#ftp/" "/")("#news." "."))'
# s = '(("" ".")) NIL NIL'
# # Use regex to find all namespace patterns
# namespaces = re.findall(r'\(\(.*?\)\)', s)

# # Clean each namespace by removing parentheses and quotes
# cleaned_namespaces = []
# for ns in namespaces:
#     # Remove outer parentheses and split inner pairs
#     print(f"ns: {ns}")
#     _extract_namespace(ns)
# d = imap.authenticate('PLAIN', lambda _: auth_string)
# print(d)
# imap.select("INBOX")
# m = imap.fetch("1:*", "(UID FLAGS)")
# print(m)
# m = imap.uid('STORE', "1,2", "+FLAGS", ("banane"))
# # # m = imap.namespace()
# print(m)
# # m = imap.create("#footest/force")
# print(m)
# m = imap.response('CAPABILITY')
# print(m)
# typ, dat = imap.xatom("LIST", '""', '"*"', 'RETURN (STATUS (MESSAGES UNSEEN) SUBSCRIBED CHILDREN)')
# m = imap.response("LIST")
# print(m)
# m = imap.response("STATUS")
# print(m)

# m = imap.list('""', '"user.sogo-tests1@example.org.*"')
# print(m)


# m = imap.select("INBOX")
# print(m)

# m = imap.fetch("1:*", '(UID)')
# print(m)


# m = imap.uid('COPY', "36,37,5500", "StepParent")
# print(m)

# m = imap.select("StepParent")
# print(m)

# m = imap.select("StepParent")
# print(m)

# m = imap.list()
# print(m)

# imap.sort()
# m = imap.status("INBOX2", '(MESSAGES UNSEEN)')
# print(m)

# m = imap.rename("AAAAA", "xyz")
# print(m)

# imap.create("bachibouzouc")
# m = imap.select("INBOX")
# m = imap.getacl("INBOX")
# print(m)
# # m = imap.setacl("INBOX", "bananae", "lr")
# print(m)
# m = imap.expunge()
# print(m)


# m = imap.search(None, "(NOT DELETED BEFORE 7-Mar-2026)")
# print(m)
# m = imap.uid('FETCH', "35", "(UID FLAGS RFC822)")
# print(m)

# m = imap.uid('FETCH', "35", "(BODY.PEEK[] FLAGS UID)")
# print(m)

# def parse_uids_from_bytes(byte_data):
#     current_uid = []
#     for byte in byte_data:
#         if byte == 32:  # 32 is the ASCII code for space
#             if current_uid:  # Avoid yielding empty strings
#                 yield b''.join(current_uid).decode('utf-8')
#                 current_uid = []
#         else:
#             current_uid.append(bytes([byte]))
#     if current_uid:  # Yield the last UID if there's no trailing space
#         yield b''.join(current_uid).decode('utf-8')

# print(list(parse_uids_from_bytes(m[1][0])))

# m = imap.status("AAAAA")
# imap.get
# print(m)
# for x in m:
#     x = x.decode()
#     # Extract flags
#     flags_match = re.search(r'\((.*?)\)', x)
#     flags = flags_match.group(1).split() if flags_match else []

#     # Extract delimiter and name
#     delimiter_match = re.search(r'"(.*?)"\s+(?:"(.*?)"|(\S+))', x)
#     if delimiter_match:
#         delimiter = delimiter_match.group(1)
#         name = delimiter_match.group(2) or delimiter_match.group(3)
#     else:
#         delimiter, name = None, None
#     print("Flags:", flags)
#     print("Delimiter:", delimiter)
#     print("Name:", name)

# m = imap.select("Sent")
# print(m)
# m = imap.response('FLAGS')
# print(m)
# m = imap.response('EXISTS')
# print(m)
# m = imap.response('RECENT')
# print(m)
# m = imap.response('UIDVALIDITY')
# print(m)


# m = imap.uid('COPY', str(57), "ban46546ane")
# print(m)
# m = imap.select("INBOX")
# m = imap.uid('STORE', str(57), "+FLAGS", "boite")
# m = imap.fetch("1", '(BODY.PEEK[] UID)')
# m = imap.uid('FETCH', '48, 49, 53', '(BODY.PEEK[] FLAGS UID)')

# print(m)

# m = imap.list('""', '"*"')
# print(m)

# for data in datas:
#     item_str=data.decode()
#     print(item_str)
#     name_match = re.search(r'"[^"]*"\s+"([^"]+)"', item_str)
#     print(name_match)
#     if not name_match:
#         name_match = re.search(r'"[^"]*"\s+(\S+)', item_str)
#     print(name_match)

#     folder_path=""
#     if name_match:
#         folder_path = name_match.group(1)

#     print(folder_path)
# print(m)

# # Lister les boîtes
# print("LIST:", imap.list())

# # Sélection INBOX
# typ, data = imap.select("INBOX")
# print("SELECT INBOX:", typ, data)

# # Statut boîte
# print("STATUS INBOX:", imap.status("INBOX", "(MESSAGES UNSEEN RECENT)"))

# # Chercher tous les mails
# typ, data = imap.search(None, "ALL")
# print("SEARCH ALL:", data)

# # Chercher non lus
# typ, data = imap.search(None, "UNSEEN")
# print("SEARCH UNSEEN:", data)

# imap.close()
# imap.logout()
