from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.CalEventDeserializer import CalEventDeserializer
from app.module.calendar.serializer.CalEventDeserializerDict import CalEventDeserializerDict


class CalTaskDeserializerDict(CalEventDeserializer[dict]):
    """Deserializes a task API dict into a VTODO CalEvent (component_type=task).

    Thin wrapper over CalEventDeserializerDict mapping the task-only ``date_due`` onto the model's
    date_end. A VTODO carries no mandatory start, but date_start is stored NOT NULL, so one is
    derived on creation.
    """

    def __init__(self) -> None:
        self._event_deserializer: CalEventDeserializerDict = CalEventDeserializerDict()

    def deserialize(self, data: dict[str, Any]) -> CalEvent:
        body: dict[str, Any] = self._map_task_fields(data)
        # Anchor a start-less VTODO on its due date rather than on the current time: a task entered
        # after it was due would otherwise get a start later than its end, and range queries - which
        # test start <= window_end AND end >= window_start - can never match an inverted interval,
        # making the task unreachable. With no due date either, now is the only anchor left.
        body["date_start"] = (
            body.get("date_start") or body.get("date_end") or datetime.now(timezone.utc).isoformat()
        )
        body["component_type"] = ComponentType.TASK.value
        return self._event_deserializer.deserialize(body)

    def deserialize_with_update(self, origin: CalEvent, update: dict | CalEvent) -> CalEvent:
        """Apply a partial task update; date_due is mapped to date_end before delegating."""
        if isinstance(update, CalEvent):
            return update
        return self._event_deserializer.deserialize_with_update(origin, self._map_task_fields(update))

    @staticmethod
    def _map_task_fields(body: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of body with the task-only ``date_due`` renamed to the model's date_end."""
        mapped: dict[str, Any] = dict(body)
        if "date_due" in mapped:
            mapped["date_end"] = mapped.pop("date_due")
        return mapped
