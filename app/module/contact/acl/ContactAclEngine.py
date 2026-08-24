from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.model.enums.ContactShareLevel import ContactShareLevel
from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.auth.User import User
    from app.factory.share.RepositoryAcl import AclEntry
    from app.factory.share.shareContact import ShareContact
    from app.module.contact.model.CardAddressBook import CardAddressBook


class ContactAclEngine:
    """Resolves and enforces address book permissions.

    Centralizes contact ACL logic: access-level resolution and action checks. Owner gets full
    access; a non-owner's level is resolved from the sogo6_acl-backed ``ShareContact`` when one
    is supplied, denied otherwise (e.g. legacy/unit-test callers that construct the engine
    without a share resolver).
    """

    def __init__(self, share: ShareContact | None = None) -> None:
        self._share: ShareContact | None = share

    def get_share_level(self, addressbook: CardAddressBook, user: User) -> ContactShareLevel | None:
        """Resolve the acting user's access level on an address book, or None when denied.

        The owner gets MODIFY on their own books. A non-owner's level comes from the sogo6_acl
        entry granted on this book (see ShareContact.get_user_or_anyone), or denied when none
        exists or no share resolver was supplied.
        """
        if addressbook.user_uid == user.uid:
            return ContactShareLevel.MODIFY
        if self._share is None or addressbook.key is None:
            return None
        entry: AclEntry | None = self._share.get_user_or_anyone(user.uid, addressbook.user_uid, addressbook.key)
        if entry is None:
            return None
        return self._share.to_share_level(entry.rights)

    def check_permission(self, level: ContactShareLevel | None, required: ContactShareLevel) -> None:
        """Raise ERROR_CONTACT_ACCESS_DENIED when the resolved level is below the required one.

        A None level (no access) always denies. ContactShareLevel is ordered VIEW < MODIFY, so a
        VIEW level satisfies a VIEW requirement but not a MODIFY one.
        """
        if level is None or level < required:
            raise RequestException(error=err.ERROR_CONTACT_ACCESS_DENIED)
