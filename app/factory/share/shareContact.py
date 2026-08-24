from __future__ import annotations

from typing import TYPE_CHECKING

from app.factory.share.share import Share
from app.module.contact.model.enums.ContactShareLevel import ContactShareLevel
from app.utils import constants as cs
from app.utils.strings import get_domain_from_mail

if TYPE_CHECKING:
    from app.factory.share.RepositoryAcl import AclEntry

# Discriminant stored in sogo6_acl.type for address book shares.
CONTACT_RESOURCE_TYPE: str = "addressbook"

# Rights blob granted by POST /addressbooks/{key}/share (full access, per the endpoint's contract).
FULL_MODIFY_RIGHTS: dict = {
    "can_view": True,
    "can_create_objects": True,
    "can_edit_objects": True,
    "can_erase_objects": True,
}


class ShareContact(Share):
    """Sharing for address books, backed by sogo6_acl (type='addressbook').

    The rights blob stored per (addressbook key, to_user) matches the API's
    ContactShareRightsSchema: ``{"can_view": bool, "can_create_objects": bool,
    "can_edit_objects": bool, "can_erase_objects": bool}``.

    ``rights_needed`` passed to ``check_permissions`` is the name of the right to check
    (e.g. "can_view", "can_edit_objects").
    """

    resource_type: str = CONTACT_RESOURCE_TYPE

    def get_user_or_anyone(self, for_user_uid: str, owner_uid: str, on_key: str) -> AclEntry | None:
        """Resolve the ACL entry granting for_user_uid access to on_key.

        Priority: an entry addressed specifically to for_user_uid; failing that, the "anyone"
        pseudo entry (``cs.ANYONE_TO_USER``, "<default>") - but only when for_user_uid and
        owner_uid belong to the same mail domain, since an "anyone" share only ever means
        "anyone in the owner's domain".
        """
        entry: AclEntry | None = self.get_entry(for_user_uid, on_key)
        if entry is not None:
            return entry
        user_domain: str | None = get_domain_from_mail(for_user_uid)
        owner_domain: str | None = get_domain_from_mail(owner_uid)
        if not user_domain or user_domain != owner_domain:
            return None
        return self.get_entry(cs.ANYONE_TO_USER, on_key)

    @staticmethod
    def to_share_level(rights: dict) -> ContactShareLevel | None:
        """Convert a stored rights blob into a ContactShareLevel, for ContactAclEngine.

        Any write flag (create/edit/erase) grants MODIFY (which also satisfies a VIEW check);
        otherwise can_view alone grants VIEW; a rights blob granting nothing at all denies.
        """
        if rights.get("can_create_objects") or rights.get("can_edit_objects") or rights.get("can_erase_objects"):
            return ContactShareLevel.MODIFY
        if rights.get("can_view"):
            return ContactShareLevel.VIEW
        return None

    def _rights_satisfy(self, rights: dict, rights_needed: str) -> bool:
        return bool(rights.get(rights_needed, False))
