from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContactImportResult:
    """Counters of a vCard / LDIF address book import.

    Import is an upsert keyed by uid: an entry whose uid already exists in the book updates it,
    otherwise it is inserted. ``skipped`` counts entries that failed individually (a malformed
    contact or list does not abort the whole import).
    """

    contacts_inserted: int = 0
    contacts_updated: int = 0
    lists_inserted: int = 0
    lists_updated: int = 0
    skipped: int = 0
