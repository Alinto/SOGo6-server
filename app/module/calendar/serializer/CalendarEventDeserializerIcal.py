from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone
from typing import Any, NamedTuple

from icalendar import Calendar

from app.module.calendar.model.enums.ComponentType import ComponentType
from app.module.calendar.serializer.IcalConst import COMP_VALARM, COMP_VEVENT, COMP_VTODO
from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalEvent import CalEvent
from app.module.calendar.model.CalEventRelation import CalEventRelation
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.CalReminder import CalReminder
from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalUserType import CalUserType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.RelationType import RelationType
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.serializer.CalendarEventDeserializer import CalendarEventDeserializer
from app.utils.calendar.DateTimeUtils import to_utc
from app.utils.errors import ERROR_CALENDAR_ICS_PARSE_FAILED
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_calendar

# Module-level mapping tables — built once, reused on every call.

_FREQ_MAP: dict[str, RecurrenceFrequency] = {
    "SECONDLY": RecurrenceFrequency.SECONDLY,
    "MINUTELY": RecurrenceFrequency.MINUTELY,
    "HOURLY": RecurrenceFrequency.HOURLY,
    "DAILY": RecurrenceFrequency.DAILY,
    "WEEKLY": RecurrenceFrequency.WEEKLY,
    "MONTHLY": RecurrenceFrequency.MONTHLY,
    "YEARLY": RecurrenceFrequency.YEARLY,
}

_ROLE_MAP: dict[str, AttendeeRole] = {
    "CHAIR": AttendeeRole.CHAIR,
    "REQ-PARTICIPANT": AttendeeRole.REQUIRED,
    "OPT-PARTICIPANT": AttendeeRole.OPTIONAL,
    "NON-PARTICIPANT": AttendeeRole.NON_PARTICIPANT,
}

_PARTSTAT_MAP: dict[str, AttendeeStatus] = {
    "NEEDS-ACTION": AttendeeStatus.NEEDS_ACTION,
    "ACCEPTED": AttendeeStatus.ACCEPTED,
    "DECLINED": AttendeeStatus.DECLINED,
    "TENTATIVE": AttendeeStatus.TENTATIVE,
    "DELEGATED": AttendeeStatus.DELEGATED,
}

_CUTYPE_MAP: dict[str, CalUserType] = {
    "INDIVIDUAL": CalUserType.INDIVIDUAL,
    "GROUP": CalUserType.GROUP,
    "RESOURCE": CalUserType.RESOURCE,
    "ROOM": CalUserType.ROOM,
    "UNKNOWN": CalUserType.UNKNOWN,
}

_STATUS_MAP: dict[str, EventStatus] = {
    # VEVENT statuses (RFC 5545 §3.8.1.11)
    "CONFIRMED": EventStatus.CONFIRMED,
    "TENTATIVE": EventStatus.TENTATIVE,
    "CANCELLED": EventStatus.CANCELLED,
    # VTODO statuses (RFC 5545 §3.8.1.11)
    "NEEDS-ACTION": EventStatus.NEEDS_ACTION,
    "IN-PROCESS": EventStatus.IN_PROCESS,
    "COMPLETED": EventStatus.COMPLETED,
}

_CLASS_MAP: dict[str, EventVisibility] = {
    "PUBLIC": EventVisibility.PUBLIC,
    "PRIVATE": EventVisibility.PRIVATE,
    "CONFIDENTIAL": EventVisibility.CONFIDENTIAL,
}

_RELTYPE_MAP: dict[str, RelationType] = {
    "PARENT": RelationType.PARENT,
    "CHILD": RelationType.CHILD,
    "SIBLING": RelationType.SIBLING,
}

_MS_BUSYSTATUS_MAP: dict[str, ShowAs] = {
    "FREE": ShowAs.FREE,
    "BUSY": ShowAs.BUSY,
    "TENTATIVE": ShowAs.TENTATIVE,
    "OOF": ShowAs.OUT_OF_OFFICE,
}

_ALARM_ACTION_MAP: dict[str, ReminderMethod] = {
    "DISPLAY": ReminderMethod.POPUP,
    "EMAIL": ReminderMethod.EMAIL,
    # AUDIO has no direct equivalent; treat as POPUP.
    "AUDIO": ReminderMethod.POPUP,
}

_EMPTY_START = datetime(1970, 1, 1, tzinfo=timezone.utc)


class _TextFields(NamedTuple):
    """Scalar text properties extracted from a VEVENT block."""

    uid: str
    title: str
    description: str | None
    location: str | None
    url: str | None
    sequence: int


class _ParticipantFields(NamedTuple):
    """Participant and list properties extracted from a VEVENT block."""

    organizer: CalOrganizer | None
    attendees: list[CalAttendee]
    attachments: list[CalAttachment]
    categories: list[str]
    related_to: list[CalEventRelation]
    extra_properties: dict[str, str]
    uid_parent_split: str | None


class _RecurrenceFields(NamedTuple):
    """Recurrence properties extracted from RRULE/RDATE/EXDATE/RECURRENCE-ID."""

    rule: CalRecurrenceRule | None
    exceptions: list[datetime]
    recurrence_id: datetime | None


class CalendarEventDeserializerIcal(CalendarEventDeserializer[str]):
    """
    Deserializes iCalendar format (RFC 5545) into calendar events.
    Uses the icalendar library for parsing.
    """

    # Public interface

    def deserialize(self, text: str) -> CalEvent:  # pylint: disable=arguments-renamed
        """Parse an iCalendar text and return the first VEVENT or VTODO found."""
        vevents = self.iter_vevents(text)
        if vevents:
            alarms = self._parse_alarms(vevents[0])
            return self._build_cal_event(vevents[0], alarms)
        vtodos = self.iter_vtodos(text)
        if vtodos:
            alarms = self._parse_alarms(vtodos[0])
            return self._build_cal_todo(vtodos[0], alarms)
        raise RequestException(error=ERROR_CALENDAR_ICS_PARSE_FAILED)

    def iter_vevents(self, text: str) -> list[Any]:
        """Parse a VCALENDAR string and return the raw VEVENT components."""
        try:
            cal: Calendar = Calendar.from_ical(text)
        except Exception as exc:  # pylint: disable=broad-except
            logger_calendar.exception("Failed to parse VCALENDAR")
            raise RequestException(error=ERROR_CALENDAR_ICS_PARSE_FAILED) from exc
        return [comp for comp in cal.walk() if comp.name == COMP_VEVENT]

    def iter_vtodos(self, text: str) -> list[Any]:
        """Parse a VCALENDAR string and return the raw VTODO components."""
        try:
            cal: Calendar = Calendar.from_ical(text)
        except Exception as exc:  # pylint: disable=broad-except
            logger_calendar.exception("Failed to parse VCALENDAR")
            raise RequestException(error=ERROR_CALENDAR_ICS_PARSE_FAILED) from exc
        return [comp for comp in cal.walk() if comp.name == COMP_VTODO]

    def deserialize_vevent(self, component: Any) -> CalEvent:
        """Deserialize a pre-parsed VEVENT component into a CalEvent."""
        alarms = self._parse_alarms(component)
        return self._build_cal_event(component, alarms)

    def deserialize_vtodo(self, component: Any) -> CalEvent:
        """Deserialize a pre-parsed VTODO component into a CalEvent."""
        alarms = self._parse_alarms(component)
        return self._build_cal_todo(component, alarms)

    # Component navigation

    # Property access helpers

    def _get_multi(self, component: Any, name: str) -> list[Any]:
        """Return all values of a possibly-repeated property as a list."""
        val = component.get(name)
        if val is None:
            return []
        return val if isinstance(val, list) else [val]

    def _get_str(self, component: Any, name: str, default: str = "") -> str:
        """Return a TEXT property as an unescaped Python string."""
        val = component.get(name)
        return str(val) if val is not None else default

    @staticmethod
    def _strip_mailto(value: str) -> str:
        """Remove the mailto: URI scheme prefix from a cal-address value."""
        if value.lower().startswith("mailto:"):
            return value[7:]
        return value

    @staticmethod
    def _extract_priority(component: Any) -> int:
        """Return PRIORITY as an int in the RFC 5545 §3.8.1.9 range [0, 9].

        0 means undefined; 1 is highest, 9 lowest. Out-of-range values from third-party
        producers are clamped instead of propagating non-compliant data into the model.
        """
        val = component.get("priority")
        if val is None:
            return 0
        return max(0, min(9, int(str(val))))

    def _parse_dt_prop(self, component: Any, name: str) -> tuple[datetime | None, bool, str | None]:
        """
        Parse a date/time property.
        Returns (utc_datetime, all_day, tzid_string).
        all_day is True when the property carries a DATE (not DATE-TIME) value.
        """
        prop = component.get(name)
        if prop is None:
            return None, False, None
        dt = prop.dt
        tzid: str | None = prop.params.get("TZID")
        all_day = isinstance(dt, date) and not isinstance(dt, datetime)
        return to_utc(dt), all_day, tzid

    # Field extractors

    def _extract_text_fields(self, vevent: Any) -> _TextFields:
        """
        Extract scalar text properties: UID, SUMMARY, DESCRIPTION, LOCATION,
        URL, and SEQUENCE.
        """
        seq_val = vevent.get("sequence")
        seq = int(str(seq_val)) if seq_val is not None else 0

        url_val = vevent.get("url")
        url = str(url_val).strip() if url_val is not None else None

        desc_val = vevent.get("description")
        loc_val = vevent.get("location")

        return _TextFields(
            uid=self._get_str(vevent, "uid"),
            title=self._get_str(vevent, "summary"),
            description=str(desc_val) if desc_val is not None else None,
            location=str(loc_val) if loc_val is not None else None,
            url=url,
            sequence=seq,
        )

    def _extract_dates(self, vevent: Any) -> tuple[datetime, datetime, bool, str]:
        """
        Extract DTSTART, DTEND / DURATION.
        Returns (date_start_utc, date_end_utc, all_day, timezone_str).
        """
        date_start, all_day, tzid = self._parse_dt_prop(vevent, "dtstart")
        if date_start is None:
            date_start, all_day, tzid = _EMPTY_START, False, None

        timezone_str = tzid or "UTC"

        date_end, _, _ = self._parse_dt_prop(vevent, "dtend")
        if date_end is None:
            duration_prop = vevent.get("duration")
            if duration_prop is not None:
                delta: timedelta = duration_prop.dt
                date_end = date_start + delta
            else:
                date_end = date_start

        return date_start, date_end, all_day, timezone_str

    def _extract_dates_todo(self, vtodo: Any) -> tuple[datetime, datetime, bool, str]:
        """Extract DTSTART and DUE / DURATION for a VTODO component.

        DTSTART is optional for VTODO (RFC 5545 §3.6.2); defaults to epoch.
        DUE is the VTODO equivalent of DTEND.
        """
        date_start, all_day, tzid = self._parse_dt_prop(vtodo, "dtstart")
        if date_start is None:
            date_start, all_day, tzid = _EMPTY_START, False, None

        timezone_str = tzid or "UTC"

        date_end, _, _ = self._parse_dt_prop(vtodo, "due")
        if date_end is None:
            duration_prop = vtodo.get("duration")
            if duration_prop is not None:
                delta: timedelta = duration_prop.dt
                date_end = date_start + delta
            else:
                date_end = date_start

        return date_start, date_end, all_day, timezone_str

    def _extract_status_fields(
        self,
        vevent: Any,
        default_status: EventStatus = EventStatus.CONFIRMED,
    ) -> tuple[EventStatus, EventVisibility, ShowAs]:
        """
        Extract STATUS, CLASS, TRANSP and Microsoft CDO extension.
        Returns (status, visibility, show_as).
        """
        status = _STATUS_MAP.get(self._get_str(vevent, "status", "").upper(), default_status)
        visibility = _CLASS_MAP.get(self._get_str(vevent, "class", "PUBLIC").upper(), EventVisibility.PUBLIC)

        show_as = ShowAs.BUSY
        if self._get_str(vevent, "transp", "").upper() == "TRANSPARENT":
            show_as = ShowAs.FREE

        ms_status = self._get_str(vevent, "x-microsoft-cdo-busystatus", "").upper()
        if ms_status:
            show_as = _MS_BUSYSTATUS_MAP.get(ms_status, show_as)

        return status, visibility, show_as

    def _extract_categories(self, vevent: Any) -> list[str]:
        """Extract CATEGORIES into a flat list of strings."""
        cats_raw = self._get_multi(vevent, "categories")
        categories: list[str] = []
        for cat_prop in cats_raw:
            if hasattr(cat_prop, "cats"):
                categories.extend(str(c) for c in cat_prop.cats)
            else:
                categories.append(str(cat_prop))
        return categories

    def _extract_timestamps(self, vevent: Any) -> tuple[datetime | None, datetime | None]:
        """
        Extract CREATED / DTSTAMP and LAST-MODIFIED.
        Returns (created_at, updated_at).
        DTSTAMP is used as fallback for created_at when CREATED is absent.
        """
        created_at, _, _ = self._parse_dt_prop(vevent, "created")
        if created_at is None:
            created_at, _, _ = self._parse_dt_prop(vevent, "dtstamp")

        updated_at, _, _ = self._parse_dt_prop(vevent, "last-modified")
        return created_at, updated_at

    def _extract_color(self, vevent: Any) -> str | None:
        """Extract color from COLOR (RFC 7986) or X-APPLE-CALENDAR-COLOR."""
        color = vevent.get("color")
        if color is not None:
            return str(color).strip()
        apple = vevent.get("x-apple-calendar-color")
        if apple is not None:
            return str(apple).strip()
        return None

    def _extract_recurrence(self, vevent: Any) -> _RecurrenceFields:
        """Extract RRULE, RDATE, EXDATE, and RECURRENCE-ID."""
        recurrence_rule: CalRecurrenceRule | None = None
        rrule_prop = vevent.get("rrule")
        if rrule_prop is not None:
            try:
                recurrence_rule = self._parse_rrule(rrule_prop)
            except (ValueError, KeyError) as exc:
                logger_calendar.warning("Could not parse RRULE: %s", exc)

        if recurrence_rule is not None:
            additional: list[datetime] = []
            for rdate_prop in self._get_multi(vevent, "rdate"):
                for dt_entry in getattr(rdate_prop, "dts", [rdate_prop]):
                    dt_val = getattr(dt_entry, "dt", dt_entry)
                    additional.append(to_utc(dt_val))
            recurrence_rule.additional_dates = additional

        exceptions: list[datetime] = []
        for exdate_prop in self._get_multi(vevent, "exdate"):
            for dt_entry in getattr(exdate_prop, "dts", [exdate_prop]):
                dt_val = getattr(dt_entry, "dt", dt_entry)
                exceptions.append(to_utc(dt_val))

        recurrence_id: datetime | None = None
        recid_dt, _, _ = self._parse_dt_prop(vevent, "recurrence-id")
        if recid_dt is not None:
            recurrence_id = recid_dt

        return _RecurrenceFields(recurrence_rule, exceptions, recurrence_id)

    def _extract_participant_fields(self, vevent: Any) -> _ParticipantFields:
        """
        Extract ORGANIZER, ATTENDEE, ATTACH, CATEGORIES, RELATED-TO,
        and X-* extension properties.
        """
        organizer: CalOrganizer | None = None
        org_prop = vevent.get("organizer")
        if org_prop is not None:
            organizer = self._parse_organizer(org_prop)

        related_to: list[CalEventRelation] = []
        uid_parent_split: str | None = None
        for rel_prop in self._get_multi(vevent, "related-to"):
            reltype = rel_prop.params.get("RELTYPE", "PARENT").upper()
            if reltype == "X-SOGO-SPLIT-FROM":
                # SOGo extension: this event was split from the series identified by this UID.
                uid_parent_split = str(rel_prop)
            else:
                related_to.append(CalEventRelation(
                    uid=str(rel_prop),
                    relation_type=_RELTYPE_MAP.get(reltype, RelationType.PARENT),
                ))

        extra_properties: dict[str, str] = {}
        for prop_name, prop_val in vevent.property_items():
            if prop_name.startswith("X-"):
                extra_properties[prop_name] = str(prop_val)

        return _ParticipantFields(
            organizer=organizer,
            attendees=[self._parse_attendee(p) for p in self._get_multi(vevent, "attendee")],
            attachments=[self._parse_attach(p) for p in self._get_multi(vevent, "attach")],
            categories=self._extract_categories(vevent),
            related_to=related_to,
            extra_properties=extra_properties,
            uid_parent_split=uid_parent_split,
        )

    # Component parsers

    def _parse_organizer(self, prop: Any) -> CalOrganizer:
        """Build a CalOrganizer from an ORGANIZER property (RFC 5545 §3.8.4.3)."""
        params = prop.params
        sent_by_raw = params.get("SENT-BY", "")
        return CalOrganizer(
            email=self._strip_mailto(str(prop)),
            name=params.get("CN") or None,
            sent_by=self._strip_mailto(sent_by_raw) if sent_by_raw else None,
            dir_ref=params.get("DIR") or None,
        )

    def _parse_attendee(self, prop: Any) -> CalAttendee:
        """Build a CalAttendee from an ATTENDEE property (RFC 5545 §3.8.4.1)."""
        params = prop.params
        delegated_from_raw = params.get("DELEGATED-FROM", "")
        delegated_to_raw = params.get("DELEGATED-TO", "")
        sent_by_raw = params.get("SENT-BY", "")
        return CalAttendee(
            email=self._strip_mailto(str(prop)),
            name=params.get("CN") or None,
            role=_ROLE_MAP.get(params.get("ROLE", "REQ-PARTICIPANT").upper(), AttendeeRole.REQUIRED),
            status=_PARTSTAT_MAP.get(params.get("PARTSTAT", "NEEDS-ACTION").upper(), AttendeeStatus.NEEDS_ACTION),
            rsvp=params.get("RSVP", "FALSE").upper() == "TRUE",
            cutype=_CUTYPE_MAP.get(params.get("CUTYPE", "INDIVIDUAL").upper(), CalUserType.INDIVIDUAL),
            delegated_from=self._strip_mailto(delegated_from_raw) if delegated_from_raw else None,
            delegated_to=self._strip_mailto(delegated_to_raw) if delegated_to_raw else None,
            sent_by=self._strip_mailto(sent_by_raw) if sent_by_raw else None,
            dir_ref=params.get("DIR") or None,
        )

    def _parse_attach(self, prop: Any) -> CalAttachment:
        """
        Build a CalAttachment from an ATTACH property (RFC 5545 §3.8.1.1).
        Supports both URI-based and inline Base64-encoded binary attachments.
        """
        params = prop.params
        encoding = params.get("ENCODING", "").upper()
        value_type = params.get("VALUE", "").upper()
        mime_type = params.get("FMTTYPE") or None

        if encoding == "BASE64" or value_type == "BINARY":
            try:
                data = bytes(prop)
            except TypeError:
                data = base64.b64decode(str(prop))
            return CalAttachment(data=data, mime_type=mime_type)

        return CalAttachment(url=str(prop), mime_type=mime_type)

    def _parse_rrule(self, prop: Any) -> CalRecurrenceRule | None:
        """
        Build a CalRecurrenceRule from an RRULE property (RFC 5545 §3.3.10).
        prop is a vRecur dict-like object.
        """
        freq_list = prop.get("FREQ", [])
        if not freq_list:
            return None
        freq = _FREQ_MAP.get(str(freq_list[0]).upper())
        if freq is None:
            return None

        count_list = prop.get("COUNT", [])
        count = int(str(count_list[0])) if count_list else None

        until_list = prop.get("UNTIL", [])
        until: datetime | None = None
        if until_list:
            until_raw = until_list[0]
            until = to_utc(until_raw) if isinstance(until_raw, (datetime, date)) else None

        interval_list = prop.get("INTERVAL", [])
        interval = int(str(interval_list[0])) if interval_list else 1

        wkst_list = prop.get("WKST", [])
        week_start = str(wkst_list[0]).upper() if wkst_list else "MO"

        def _int_list(key: str) -> list[int] | None:
            vals = prop.get(key, [])
            return [int(str(v)) for v in vals] if vals else None

        by_day = [str(d) for d in prop.get("BYDAY", [])] or None

        return CalRecurrenceRule(
            frequency=freq,
            interval=interval,
            until=until,
            count=count,
            by_day=by_day,
            by_month_day=_int_list("BYMONTHDAY"),
            by_month=_int_list("BYMONTH"),
            by_year_day=_int_list("BYYEARDAY"),
            by_week_no=_int_list("BYWEEKNO"),
            by_set_pos=_int_list("BYSETPOS"),
            by_hour=_int_list("BYHOUR"),
            by_minute=_int_list("BYMINUTE"),
            by_second=_int_list("BYSECOND"),
            week_start=week_start,
        )

    def _parse_alarms(self, vevent: Any) -> list[CalReminder]:
        """Build CalReminder list from all VALARM sub-components."""
        reminders: list[CalReminder] = []
        for subcomp in vevent.subcomponents:
            if subcomp.name != COMP_VALARM:
                continue
            reminder = self._parse_valarm(subcomp)
            if reminder is not None:
                reminders.append(reminder)
        return reminders

    def _parse_valarm(self, alarm: Any) -> CalReminder | None:
        """
        Build a CalReminder from a VALARM sub-component (RFC 5545 §3.6.6).
        Duration-based TRIGGER values are converted to minutes_before.
        Absolute DATE-TIME triggers are not supported and yield minutes_before=0.
        """
        action = self._get_str(alarm, "action", "DISPLAY").upper()
        method = _ALARM_ACTION_MAP.get(action, ReminderMethod.POPUP)

        trigger_prop = alarm.get("trigger")
        if trigger_prop is None:
            return None

        trigger_val = trigger_prop.dt
        if isinstance(trigger_val, timedelta):
            return CalReminder(method=method, minutes_before=int(-trigger_val.total_seconds() / 60))

        # Absolute TRIGGER DATE-TIME (RFC 5545 §3.8.6.3 VALUE=DATE-TIME form) is not modelled
        # in CalReminder, which only stores a relative offset. Falling back to 0 is correct
        # enough for the no-Agent prototype; the caller logs a single summary when this
        # happens repeatedly so it stays visible without spamming the per-alarm log.
        return CalReminder(method=method, minutes_before=0)

    # CalEvent assembler

    def _build_cal_event(self, vevent: Any, alarms: list[CalReminder]) -> CalEvent:
        """Assemble a CalEvent from a parsed VEVENT component and pre-built alarms."""
        text = self._extract_text_fields(vevent)
        date_start, date_end, all_day, timezone_str = self._extract_dates(vevent)
        status, visibility, show_as = self._extract_status_fields(vevent)
        recur = self._extract_recurrence(vevent)
        created_at, updated_at = self._extract_timestamps(vevent)
        parts = self._extract_participant_fields(vevent)
        return CalEvent(
            uid=text.uid,
            title=text.title,
            date_start=date_start,
            date_end=date_end,
            all_day=all_day,
            timezone=timezone_str,
            description=text.description,
            location=text.location,
            status=status,
            visibility=visibility,
            show_as=show_as,
            color=self._extract_color(vevent),
            sequence=text.sequence,
            priority=self._extract_priority(vevent),
            url=text.url,
            organizer=parts.organizer,
            attendees=parts.attendees,
            reminders=alarms,
            attachments=parts.attachments,
            categories=parts.categories,
            related_to=parts.related_to,
            recurrence_rule=recur.rule,
            recurrence_exceptions=recur.exceptions,
            recurrence_id=recur.recurrence_id,
            extra_properties=parts.extra_properties,
            uid_parent_split=parts.uid_parent_split,
            created_at=created_at,
            updated_at=updated_at,
            component_type=ComponentType.EVENT,
        )

    def _build_cal_todo(self, vtodo: Any, alarms: list[CalReminder]) -> CalEvent:  # pylint: disable=too-many-locals
        """Assemble a CalEvent from a parsed VTODO component and pre-built alarms."""
        text = self._extract_text_fields(vtodo)
        date_start, date_end, all_day, timezone_str = self._extract_dates_todo(vtodo)
        status, visibility, show_as = self._extract_status_fields(vtodo, EventStatus.NEEDS_ACTION)
        recur = self._extract_recurrence(vtodo)
        created_at, updated_at = self._extract_timestamps(vtodo)
        parts = self._extract_participant_fields(vtodo)

        pct_val = vtodo.get("percent-complete")
        percent_complete = int(str(pct_val)) if pct_val is not None else None
        completed_at, _, _ = self._parse_dt_prop(vtodo, "completed")

        return CalEvent(
            uid=text.uid,
            title=text.title,
            date_start=date_start,
            date_end=date_end,
            all_day=all_day,
            timezone=timezone_str,
            description=text.description,
            location=text.location,
            status=status,
            visibility=visibility,
            show_as=show_as,
            color=self._extract_color(vtodo),
            sequence=text.sequence,
            priority=self._extract_priority(vtodo),
            url=text.url,
            organizer=parts.organizer,
            attendees=parts.attendees,
            reminders=alarms,
            attachments=parts.attachments,
            categories=parts.categories,
            related_to=parts.related_to,
            recurrence_rule=recur.rule,
            recurrence_exceptions=recur.exceptions,
            recurrence_id=recur.recurrence_id,
            extra_properties=parts.extra_properties,
            uid_parent_split=parts.uid_parent_split,
            created_at=created_at,
            updated_at=updated_at,
            component_type=ComponentType.TASK,
            percent_complete=percent_complete,
            completed_at=completed_at,
        )
