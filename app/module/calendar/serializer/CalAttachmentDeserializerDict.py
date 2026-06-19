from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalAttachment import CalAttachment
from app.utils.serializer.Deserializer import Deserializer


class CalAttachmentDeserializerDict(Deserializer[dict[str, Any], CalAttachment]):
    """Deserializes a dict into a CalAttachment (RFC 5545 ATTACH)."""

    def deserialize(self, data: dict[str, Any]) -> CalAttachment:
        """Convert a dict into a CalAttachment."""
        return CalAttachment(
            filename=data.get("filename"),
            mime_type=data.get("mime_type"),
            url=data.get("url"),
            size=data.get("size"),
        )
