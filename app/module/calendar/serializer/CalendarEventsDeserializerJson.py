from __future__ import annotations

import json
from typing import Any

from app.module.calendar.serializer.CalendarEventsDeserializer import CalendarEventsDeserializer
from app.module.calendar.serializer.CalendarEventDeserializerJson import CalendarEventDeserializerJson
from app.module.calendar.model.CalEvent import CalEvent
from app.utils import errors as err
from app.utils.exceptions import RequestException


class CalendarEventsDeserializerJson(CalendarEventsDeserializer):
    """
    Deserializes a JSON string into a list of CalEvent objects.
    Expects a JSON array of event objects, or a dict with an "events" key.
    """

    def __init__(self, event_deserializer: CalendarEventDeserializerJson | None = None) -> None:
        self._event_deserializer: CalendarEventDeserializerJson = event_deserializer or CalendarEventDeserializerJson()

    def deserialize(self, text: str) -> list[CalEvent]:
        """Deserialize a JSON string into a list of CalEvent objects."""
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RequestException(error=err.ERROR_CALENDAR_JSON_PARSE_FAILED) from exc
        return self.from_list(data if isinstance(data, list) else data.get("events", []))

    def from_list(self, items: list[dict[str, Any]]) -> list[CalEvent]:
        """Convert a list of event dicts into CalEvent objects."""
        return [self._event_deserializer.from_dict(item) for item in items]
