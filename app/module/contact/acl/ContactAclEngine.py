from __future__ import annotations

from typing import TYPE_CHECKING

from app.module.contact.model.enums.ContactShareLevel import ContactShareLevel
from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.auth.User import User
    from app.module.contact.model.CardAddressBook import CardAddressBook


class ContactAclEngine:
    """Resolves and enforces address book permissions.

    Centralizes contact ACL logic: access-level resolution and action checks. Currently stubbed -
    the owner gets MODIFY on their own books, a non-owner is denied. Will be connected to the
    centralized ACL module (internal sharing) when it is implemented.
    """

    def get_share_level(self, addressbook: CardAddressBook, user: User) -> ContactShareLevel | None:
        """Resolve the acting user's access level on an address book, or None when denied.

        The owner gets MODIFY on their own books; a non-owner is denied (stub) until the ACL module
        provides shared levels.
        """
        if addressbook.user_uid == user.uid:
            return ContactShareLevel.MODIFY
        # TODO: look up shared permissions from the centralized ACL module
        return None

    def check_permission(self, level: ContactShareLevel | None, required: ContactShareLevel) -> None:
        """Raise ERROR_CONTACT_ACCESS_DENIED when the resolved level is below the required one.

        A None level (no access) always denies. ContactShareLevel is ordered VIEW < MODIFY, so a
        VIEW level satisfies a VIEW requirement but not a MODIFY one.
        """
        if level is None or level < required:
            raise RequestException(error=err.ERROR_CONTACT_ACCESS_DENIED)
