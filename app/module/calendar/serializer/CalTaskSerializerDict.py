from __future__ import annotations

from typing import Any

from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.serializer.CalEventSerializer import CalEventSerializer
from app.module.calendar.serializer.CalEventSerializerDict import CalEventSerializerDict


class CalTaskSerializerDict(CalEventSerializer[dict]):
    """Serializes a VTODO (a CalEvent with component_type=task) to the task API dict.

    Thin wrapper over CalEventSerializerDict: a task's due date lives on the model's date_end but is
    exposed as ``date_due`` in the task representation.
    """

    def __init__(self) -> None:
        self._event_serializer: CalEventSerializerDict = CalEventSerializerDict()

    def serialize(self, data: CalEvent) -> dict[str, Any]:
        result: dict[str, Any] = self._event_serializer.serialize(data)
        result["date_due"] = result.pop("date_end", None)
        return result
