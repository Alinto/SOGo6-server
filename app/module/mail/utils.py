from typing import Dict, List, Any

# Mapping constants to centralize conversions between SOGo rights and IMAP ACL chars.
RIGHTS_MAP: Dict[str, str] = {
    "userCanViewFolder": "lr",            # lookup + read
    "userCanReadMails": "s",              # keep seen/unseen information (s)
    "userCanMarkMailsRead": "w",          # write (w)
    "userCanInsertMails": "i",            # insert (i)
    "userCanPostMails": "p",              # post (p)
    "userCanCreateSubfolders": "k",       # create subfolders (k) (c is obsolete/alias)
    "userCanRemoveFolder": "x",           # delete mailbox (x)
    "userCanEraseMails": "t",             # delete messages (t)
    "userCanExpungeFolder": "e",          # expunge (e)
    "userCanWriteMails": "w",             # same as mark mails read/write flags
    "userIsAdministrator": "a",           # administer (a)
}

# IMAP char -> list of SOGo keys to set when char present.
IMAP_TO_SOGO: Dict[str, List[str]] = {
    "s": ["userCanReadMails"],
    "w": ["userCanMarkMailsRead", "userCanWriteMails"],
    "i": ["userCanInsertMails"],
    "p": ["userCanPostMails"],
    "k": ["userCanCreateSubfolders"],
    "c": ["userCanCreateSubfolders"],  # obsolete alias for create
    "x": ["userCanRemoveFolder"],
    "t": ["userCanEraseMails"],
    "e": ["userCanExpungeFolder"],
    "d": ["userCanRemoveFolder", "userCanEraseMails", "userCanExpungeFolder"],  # obsolete -> x+t+e
    "a": ["userIsAdministrator"],
    # 'l' and 'r' are treated specially (see below)
}

def convert_rights_to_imap(rights_dict: Dict[str, Any]) -> str:
    """Convert SOGo rights dictionary to IMAP ACL rights string using RIGHTS_MAP.

    Preserves order defined in RIGHTS_MAP and removes duplicates.
    """
    if not rights_dict or not isinstance(rights_dict, dict):
        return ""

    imap_chars: List[str] = []
    seen = set()

    for sogo_key, imap_seq in RIGHTS_MAP.items():
        if rights_dict.get(sogo_key):
            for ch in imap_seq:
                if ch not in seen:
                    seen.add(ch)
                    imap_chars.append(ch)

    return "".join(imap_chars)

def convert_imap_to_rights(imap_rights: str) -> Dict[str, int]:
    """Convert IMAP ACL rights string to SOGo rights dictionary using IMAP_TO_SOGO.

    Behaviours preserved:
    - userCanViewFolder is set only when both 'l' and 'r' present.
    - 'd' expands to x,t,e as before.
    """
    # Initialize all rights to 0
    sogo_rights: Dict[str, int] = {
        "userCanViewFolder": 0,
        "userCanReadMails": 0,
        "userCanMarkMailsRead": 0,
        "userCanInsertMails": 0,
        "userCanPostMails": 0,
        "userCanCreateSubfolders": 0,
        "userCanRemoveFolder": 0,
        "userCanEraseMails": 0,
        "userCanExpungeFolder": 0,
        "userCanWriteMails": 0,
        "userIsAdministrator": 0
    }

    if not imap_rights:
        return sogo_rights

    rights_lower = imap_rights.lower()

    # Track presence of 'l' and 'r' for userCanViewFolder
    has_l = 'l' in rights_lower
    has_r = 'r' in rights_lower

    # Set flags based on IMAP_TO_SOGO mapping
    for ch, sogo_keys in IMAP_TO_SOGO.items():
        if ch in rights_lower:
            for key in sogo_keys:
                sogo_rights[key] = 1

    # Now handle l+r -> userCanViewFolder (must have both)
    if has_l and has_r:
        sogo_rights["userCanViewFolder"] = 1

    return sogo_rights
