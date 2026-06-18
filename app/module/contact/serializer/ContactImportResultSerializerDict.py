from __future__ import annotations

from typing import Any

from app.module.contact.model.ContactImportResult import ContactImportResult
from app.utils.serializer.Serializer import Serializer


class ContactImportResultSerializerDict(Serializer[ContactImportResult, dict[str, Any]]):
    """Serializes a ContactImportResult to a dict for API responses."""

    def serialize(self, data: ContactImportResult) -> dict[str, Any]:
        return {
            "contacts_inserted": data.contacts_inserted,
            "contacts_updated": data.contacts_updated,
            "lists_inserted": data.lists_inserted,
            "lists_updated": data.lists_updated,
            "skipped": data.skipped,
        }
