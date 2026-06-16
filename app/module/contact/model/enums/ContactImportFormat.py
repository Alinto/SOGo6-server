from __future__ import annotations

from enum import Enum


class ContactImportFormat(str, Enum):
    """Format a contact was imported from.

    Provenance for the contents of extra_properties: an unknown entry's dialect (vCard 3.0 vs 4.0
    property, or an LDIF attribute) cannot be told apart without knowing the import format.
    UNDEFINED is used for contacts created through the JSON API rather than imported.
    """
    UNDEFINED = "undefined"
    VCARD3 = "vcard3"
    VCARD4 = "vcard4"
    LDIF = "ldif"
