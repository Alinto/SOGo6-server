from __future__ import annotations


from app.factory.share.share import Share

# Discriminant stored in sogo6_acl.type for mail folder shares.
FOLDER_RESOURCE_TYPE: str = "folder"

# IMAP ACL codes exposed through the simplified `permissions` list (see FolderShareEntrySchema).
# Each code maps 1:1 to a boolean flag of the advanced `rights` object.
FOLDER_SHARE_PERMISSION_CODES: list[str] = ["l", "r", "s", "w", "i", "p", "k", "x", "t", "e", "a"]

# code IMAP -> SOGo folder right name. The single correspondence table between the API's
# simplified `permissions` codes, the advanced `rights` flags, and the raw IMAP ACL characters
# sent to the mail server (see ClientImap.set_acl_raw/get_acl_raw). Lives here (not in the API
# schemas) so both the API layer and ModuleMail can share it without violating layering.
FOLDER_PERMISSION_CODE_TO_RIGHT: dict[str, str] = {
    "l": "user_can_view_folder",          # Voir le dossier
    "r": "user_can_read_mails",           # Lire les mails
    "s": "user_can_mark_mails_read",      # Marquer comme lu/non lu
    "w": "user_can_write_mails",          # Modifier les indicateurs des mails
    "i": "user_can_insert_mails",         # Insérer, copier des mails
    "p": "user_can_post_mails",           # Envoyer des mails
    "k": "user_can_create_subfolders",    # Créer des sous-dossiers
    "x": "user_can_remove_folder",        # Supprimer le dossier
    "t": "user_can_erase_mails",          # Effacer les mails
    "e": "user_can_expunge_folder",       # Purger le dossier
    "a": "user_is_administrator",         # Administrer les droits du dossier
}


def rights_to_imap_permissions(rights: dict[str, int]) -> str:
    """Convert a resolved folder rights dict into the ordered raw IMAP ACL rights string.

    :param rights: full folder rights dict (one 0/1 flag per FOLDER_PERMISSION_CODE_TO_RIGHT entry).
    :return: IMAP ACL characters to grant, in FOLDER_PERMISSION_CODE_TO_RIGHT's canonical order.
    """
    return "".join(code for code, right in FOLDER_PERMISSION_CODE_TO_RIGHT.items() if rights.get(right))


def imap_permissions_to_rights(imap_rights: str) -> dict[str, int]:
    """Convert a raw IMAP ACL rights string into the full folder rights dict (0/1 flags).

    :param imap_rights: raw IMAP ACL characters as returned by GETACL (e.g. "lrswipkxtea").
    :return: full folder rights dict, one 0/1 flag per FOLDER_PERMISSION_CODE_TO_RIGHT entry.
    """
    granted = set(imap_rights)
    return {right: (1 if code in granted else 0) for code, right in FOLDER_PERMISSION_CODE_TO_RIGHT.items()}


class ShareMailFolder(Share):
    """Sharing for mail folders, backed by sogo6_acl (type='folder').

    The rights blob stored per (folder key, to_user) matches the API's
    FolderShareRightsInputSchema: one 0/1 flag per IMAP ACL right (see
    ``FOLDER_PERMISSION_CODE_TO_RIGHT`` above).

    ``rights_needed`` passed to ``check_permissions`` is the name of the right to check
    (e.g. "user_can_read_mails").
    """

    resource_type: str = FOLDER_RESOURCE_TYPE

    def _rights_satisfy(self, rights: dict, rights_needed: str) -> bool:
        return bool(rights.get(rights_needed, False))
