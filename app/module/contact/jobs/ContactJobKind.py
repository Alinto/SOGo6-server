"""Target granularity of a contact import/export job."""
from __future__ import annotations

from enum import StrEnum


class ContactJobKind(StrEnum):
    """Which scope an import/export job operates on.

    ADDRESSBOOK imports/exports a whole book (import creates a new book), CONTACT and LIST
    operate on a single item inside an existing book.
    """

    ADDRESSBOOK = "addressbook"
    CONTACT = "contact"
    LIST = "list"
