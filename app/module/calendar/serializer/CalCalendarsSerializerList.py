from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.module.calendar.serializer.CalCalendarSerializerDict import CalCalendarSerializerDict
from app.module.calendar.serializer.CalCalendarsSerializer import CalCalendarsSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalCalendar import CalCalendar


class CalCalendarsSerializerList(CalCalendarsSerializer[list]):
    """Converts a list of CalCalendar objects to a list of dicts."""

    def __init__(self, cal_serializer: CalCalendarSerializerDict | None = None) -> None:
        self._cal_serializer: CalCalendarSerializerDict = cal_serializer or CalCalendarSerializerDict()

    def serialize(self, data: list[CalCalendar]) -> list[dict[str, Any]]:
        return [self._cal_serializer.serialize(cal) for cal in data]
