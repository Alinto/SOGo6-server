from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalAttachment import CalAttachment
from app.utils.serializer.Serializer import Serializer


class CalAttachmentSerializerDict(Serializer[CalAttachment, dict[str, Any]]):
    """Serializes a CalAttachment (RFC 5545 ATTACH) to a dict."""

    def serialize(self, data: CalAttachment) -> dict[str, Any]:
        """Convert a CalAttachment to its dict representation."""
        return {"filename": data.filename, "mime_type": data.mime_type, "url": data.url, "size": data.size}
