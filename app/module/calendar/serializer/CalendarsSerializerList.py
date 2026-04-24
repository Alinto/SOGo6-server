from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.calendar.serializer.CalendarSerializerDict import CalendarSerializerDict
from app.module.calendar.serializer.CalendarsSerializer import CalendarsSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar


class CalendarsSerializerList(CalendarsSerializer[list]):
    """Converts a list of CalCalendar objects to a list of dicts."""

    def __init__(self, cal_serializer: CalendarSerializerDict | None = None) -> None:
        self._cal_serializer: CalendarSerializerDict = cal_serializer or CalendarSerializerDict()

    def serialize(self, data: list[CalCalendar]) -> list[dict[str, Any]]:
        return [self._cal_serializer.serialize(cal) for cal in data]
