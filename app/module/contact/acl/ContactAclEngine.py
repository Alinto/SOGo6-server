from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.auth.User import User
    from app.factory.share.shareContact import ShareContact
    from app.module.contact.model.CardAddressBook import CardAddressBook


class ContactAclEngine:
    """Resolves and enforces address book permissions.

    Centralizes contact ACL logic. Each action checks the right it actually needs (the names of
    the rights blob: can_view, can_create_objects, can_edit_objects, can_erase_objects), like
    the calendar engine keeps can_create / can_delete apart. The owner holds every right; a
    non-owner's rights come from the sogo6_acl-backed ``ShareContact`` when one is supplied,
    denied otherwise (e.g. legacy/unit-test callers that construct the engine without a share
    resolver).
    """

    def __init__(self, share: ShareContact | None = None) -> None:
        self._share: ShareContact | None = share

    def has_right(self, addressbook: CardAddressBook, user: User, right: str) -> bool:
        """Return True if the acting user holds the named right on the address book.

        The owner holds every right on their own books. A non-owner's rights come from the
        sogo6_acl entry granted on this book (see ShareContact.get_user_or_anyone), or are
        denied when none exists or no share resolver was supplied.
        """
        if addressbook.user_uid == user.uid:
            return True
        if self._share is None or addressbook.key is None:
            return False
        return self._share.has_right(user.uid, addressbook.user_uid, addressbook.key, right)

    def check_permission(self, addressbook: CardAddressBook, user: User, *rights: str) -> None:
        """Raise ERROR_CONTACT_ACCESS_DENIED unless the acting user holds every one of ``rights``."""
        if not all(self.has_right(addressbook, user, right) for right in rights):
            raise RequestException(error=err.ERROR_CONTACT_ACCESS_DENIED)
