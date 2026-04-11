from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from icalendar import Alarm, Calendar, Event, vBinary, vCalAddress, vRecur, vText

from app.module.calendar.serializer.IcalConst import CALSCALE, ICAL_VERSION, PRODID
from app.module.calendar.model.CalAttachment import CalAttachment
from app.module.calendar.model.CalAttendee import CalAttendee
from app.module.calendar.model.CalOrganizer import CalOrganizer
from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule
from app.module.calendar.model.enums.AttendeeRole import AttendeeRole
from app.module.calendar.model.enums.AttendeeStatus import AttendeeStatus
from app.module.calendar.model.enums.CalUserType import CalUserType
from app.module.calendar.model.enums.EventStatus import EventStatus
from app.module.calendar.model.enums.EventVisibility import EventVisibility
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.module.calendar.model.enums.RelationType import RelationType
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.calendar.model.enums.ShowAs import ShowAs
from app.module.calendar.serializer.CalendarEventSerializer import CalendarEventSerializer

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent

# ---------------------------------------------------------------------------
# Module-level reverse mapping tables — enum → RFC 5545 string value.
# ---------------------------------------------------------------------------

_STATUS_OUT: dict[EventStatus, str] = {
    EventStatus.CONFIRMED: "CONFIRMED",
    EventStatus.TENTATIVE: "TENTATIVE",
    EventStatus.CANCELLED: "CANCELLED",
}

_CLASS_OUT: dict[EventVisibility, str] = {
    EventVisibility.PUBLIC: "PUBLIC",
    EventVisibility.PRIVATE: "PRIVATE",
    EventVisibility.CONFIDENTIAL: "CONFIDENTIAL",
}

_ROLE_OUT: dict[AttendeeRole, str] = {
    AttendeeRole.CHAIR: "CHAIR",
    AttendeeRole.REQUIRED: "REQ-PARTICIPANT",
    AttendeeRole.OPTIONAL: "OPT-PARTICIPANT",
    AttendeeRole.NON_PARTICIPANT: "NON-PARTICIPANT",
}

_PARTSTAT_OUT: dict[AttendeeStatus, str] = {
    AttendeeStatus.NEEDS_ACTION: "NEEDS-ACTION",
    AttendeeStatus.ACCEPTED: "ACCEPTED",
    AttendeeStatus.DECLINED: "DECLINED",
    AttendeeStatus.TENTATIVE: "TENTATIVE",
    AttendeeStatus.DELEGATED: "DELEGATED",
}

_CUTYPE_OUT: dict[CalUserType, str] = {
    CalUserType.INDIVIDUAL: "INDIVIDUAL",
    CalUserType.GROUP: "GROUP",
    CalUserType.RESOURCE: "RESOURCE",
    CalUserType.ROOM: "ROOM",
    CalUserType.UNKNOWN: "UNKNOWN",
}

_FREQ_OUT: dict[RecurrenceFrequency, str] = {
    RecurrenceFrequency.SECONDLY: "SECONDLY",
    RecurrenceFrequency.MINUTELY: "MINUTELY",
    RecurrenceFrequency.HOURLY: "HOURLY",
    RecurrenceFrequency.DAILY: "DAILY",
    RecurrenceFrequency.WEEKLY: "WEEKLY",
    RecurrenceFrequency.MONTHLY: "MONTHLY",
    RecurrenceFrequency.YEARLY: "YEARLY",
}

_ACTION_OUT: dict[ReminderMethod, str] = {
    ReminderMethod.POPUP: "DISPLAY",
    ReminderMethod.EMAIL: "EMAIL",
}

_RELTYPE_OUT: dict[RelationType, str] = {
    RelationType.PARENT: "PARENT",
    RelationType.CHILD: "CHILD",
    RelationType.SIBLING: "SIBLING",
}


class CalendarEventSerializerIcal(CalendarEventSerializer):
    """
    Serializes calendar events to iCalendar format (RFC 5545).
    Uses the icalendar library for encoding, folding, and escaping.
    """

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def serialize(self, event: CalEvent) -> str:
        """
        Serialize a CalEvent to a VCALENDAR string compliant with RFC 5545.
        The output uses CRLF line endings and 75-octet line folding.
        """
        return self.build_vcalendar([event])

    def build_vcalendar(self, events: list[CalEvent]) -> str:
        """Wrap a list of CalEvent objects in a VCALENDAR and return the ICS string."""
        cal: Calendar = Calendar()
        cal.add("prodid", PRODID)
        cal.add("version", ICAL_VERSION)
        cal.add("calscale", CALSCALE)
        for event in events:
            cal.add_component(self._build_vevent(event))
        return cal.to_ical().decode("utf-8")

    def to_vevent(self, event: CalEvent) -> Event:
        """Build a VEVENT component from a CalEvent without the VCALENDAR wrapper."""
        return self._build_vevent(event)

    # ------------------------------------------------------------------
    # VEVENT builder
    # ------------------------------------------------------------------

    def _build_vevent(self, event: CalEvent) -> Event:
        """Build a complete VEVENT component from a CalEvent."""
        vevent: Event = Event()
        self._add_core(vevent, event)
        self._add_dates(vevent, event)
        self._add_status(vevent, event)
        self._add_participants(vevent, event)
        self._add_recurrence(vevent, event)
        self._add_attachments(vevent, event)
        self._add_conference(vevent, event)
        self._add_alarms(vevent, event)
        for prop_name, prop_value in event.extra_properties.items():
            vevent.add(prop_name, prop_value)
        return vevent

    # ------------------------------------------------------------------
    # Property group builders
    # ------------------------------------------------------------------

    def _add_core(self, vevent: Event, event: CalEvent) -> None:
        """Add UID, SUMMARY, DESCRIPTION, LOCATION, URL, SEQUENCE, CATEGORIES, COLOR."""
        vevent.add("uid", event.uid)
        vevent.add("summary", event.title)
        if event.description:
            vevent.add("description", event.description)
        if event.location:
            vevent.add("location", event.location)
        if event.url:
            vevent.add("url", event.url)
        vevent.add("sequence", event.sequence)
        if event.categories:
            vevent.add("categories", event.categories)
        for rel in event.related_to:
            rel_val = vText(rel.uid)
            rel_val.params["RELTYPE"] = _RELTYPE_OUT.get(rel.relation_type, "PARENT")
            vevent.add("related-to", rel_val, encode=False)
        if event.color:
            vevent.add("color", event.color)

    def _add_dates(self, vevent: Event, event: CalEvent) -> None:
        """Add DTSTART, DTEND, DTSTAMP, CREATED, LAST-MODIFIED, RECURRENCE-ID."""
        if event.all_day:
            vevent.add("dtstart", event.start_date.date())
            vevent.add("dtend", event.end_date.date())
        else:
            vevent.add("dtstart", event.start_date)
            vevent.add("dtend", event.end_date)
        vevent.add("dtstamp", datetime.now(timezone.utc))
        if event.created_at:
            vevent.add("created", event.created_at)
        if event.updated_at:
            vevent.add("last-modified", event.updated_at)
        if event.recurrence_id:
            recid = event.recurrence_id.date() if event.all_day else event.recurrence_id
            vevent.add("recurrence-id", recid)

    def _add_status(self, vevent: Event, event: CalEvent) -> None:
        """Add STATUS, CLASS, TRANSP, and optional X-MICROSOFT-CDO-BUSYSTATUS."""
        vevent.add("status", _STATUS_OUT.get(event.status, "CONFIRMED"))
        vevent.add("class", _CLASS_OUT.get(event.visibility, "PUBLIC"))
        vevent.add("transp", "TRANSPARENT" if event.show_as == ShowAs.FREE else "OPAQUE")
        if event.show_as == ShowAs.TENTATIVE:
            vevent.add("x-microsoft-cdo-busystatus", "TENTATIVE")
        elif event.show_as == ShowAs.OUT_OF_OFFICE:
            vevent.add("x-microsoft-cdo-busystatus", "OOF")

    def _add_participants(self, vevent: Event, event: CalEvent) -> None:
        """Add ORGANIZER and ATTENDEE properties."""
        if event.organizer:
            vevent.add("organizer", self._format_organizer(event.organizer), encode=False)
        for attendee in event.attendees:
            vevent.add("attendee", self._format_attendee(attendee), encode=False)

    def _add_recurrence(self, vevent: Event, event: CalEvent) -> None:
        """Add RRULE, RDATE, and EXDATE properties."""
        if event.recurrence_rule:
            vevent.add("rrule", self._format_rrule(event.recurrence_rule))
            for rdate in event.recurrence_rule.additional_dates:
                vevent.add("rdate", rdate)
        for exdate in event.recurrence_exceptions:
            vevent.add("exdate", exdate)

    def _add_attachments(self, vevent: Event, event: CalEvent) -> None:
        """Add ATTACH properties for each attachment."""
        for attach in event.attachments:
            self._add_attach(vevent, attach)

    def _add_conference(self, vevent: Event, event: CalEvent) -> None:
        """Add X-CONFERENCE extension properties from conference_data."""
        if not event.conference_data:
            return
        cd = event.conference_data
        if cd.url:
            vevent.add("x-conference-url", cd.url)
        if cd.conference_id:
            vevent.add("x-conference-id", cd.conference_id)
        for ep in cd.entry_points:
            ep_val = vText(ep.uri)
            ep_val.params["TYPE"] = ep.type
            if ep.label:
                ep_val.params["LABEL"] = ep.label
            vevent.add("x-conference-entrypoint", ep_val, encode=False)

    def _add_alarms(self, vevent: Event, event: CalEvent) -> None:
        """Add VALARM sub-components for each reminder."""
        for reminder in event.reminders:
            alarm: Alarm = Alarm()
            alarm.add("action", _ACTION_OUT.get(reminder.method, "DISPLAY"))
            alarm.add("trigger", timedelta(minutes=-reminder.minutes_before))
            alarm.add("description", "Reminder")
            vevent.add_component(alarm)

    # ------------------------------------------------------------------
    # Component formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _format_organizer(organizer: CalOrganizer) -> vCalAddress:
        """Format a CalOrganizer as a vCalAddress with parameters."""
        addr: vCalAddress = vCalAddress(f"mailto:{organizer.email}")
        if organizer.name:
            addr.params["CN"] = organizer.name
        if organizer.sent_by:
            addr.params["SENT-BY"] = f"mailto:{organizer.sent_by}"
        if organizer.dir_ref:
            addr.params["DIR"] = organizer.dir_ref
        return addr

    @staticmethod
    def _format_attendee(attendee: CalAttendee) -> vCalAddress:
        """Format a CalAttendee as a vCalAddress with parameters."""
        addr: vCalAddress = vCalAddress(f"mailto:{attendee.email}")
        if attendee.name:
            addr.params["CN"] = attendee.name
        addr.params["ROLE"] = _ROLE_OUT.get(attendee.role, "REQ-PARTICIPANT")
        addr.params["PARTSTAT"] = _PARTSTAT_OUT.get(attendee.status, "NEEDS-ACTION")
        cutype = _CUTYPE_OUT.get(attendee.cutype, "INDIVIDUAL")
        if cutype != "INDIVIDUAL":
            addr.params["CUTYPE"] = cutype
        if attendee.rsvp:
            addr.params["RSVP"] = "TRUE"
        if attendee.delegated_from:
            addr.params["DELEGATED-FROM"] = f"mailto:{attendee.delegated_from}"
        if attendee.delegated_to:
            addr.params["DELEGATED-TO"] = f"mailto:{attendee.delegated_to}"
        if attendee.sent_by:
            addr.params["SENT-BY"] = f"mailto:{attendee.sent_by}"
        if attendee.dir_ref:
            addr.params["DIR"] = attendee.dir_ref
        return addr

    @staticmethod
    def _format_rrule(rule: CalRecurrenceRule) -> vRecur:  # pylint: disable=too-many-branches
        """Format a CalRecurrenceRule as a vRecur object."""
        parts = [f"FREQ={_FREQ_OUT[rule.frequency]}"]
        if rule.interval != 1:
            parts.append(f"INTERVAL={rule.interval}")
        if rule.until is not None:
            parts.append(f"UNTIL={rule.until.strftime('%Y%m%dT%H%M%SZ')}")
        elif rule.count is not None:
            parts.append(f"COUNT={rule.count}")
        if rule.by_day:
            parts.append(f"BYDAY={','.join(rule.by_day)}")
        if rule.by_month_day:
            parts.append(f"BYMONTHDAY={','.join(str(d) for d in rule.by_month_day)}")
        if rule.by_month:
            parts.append(f"BYMONTH={','.join(str(m) for m in rule.by_month)}")
        if rule.by_year_day:
            parts.append(f"BYYEARDAY={','.join(str(d) for d in rule.by_year_day)}")
        if rule.by_week_no:
            parts.append(f"BYWEEKNO={','.join(str(w) for w in rule.by_week_no)}")
        if rule.by_set_pos:
            parts.append(f"BYSETPOS={','.join(str(p) for p in rule.by_set_pos)}")
        if rule.by_hour:
            parts.append(f"BYHOUR={','.join(str(h) for h in rule.by_hour)}")
        if rule.by_minute:
            parts.append(f"BYMINUTE={','.join(str(m) for m in rule.by_minute)}")
        if rule.by_second:
            parts.append(f"BYSECOND={','.join(str(s) for s in rule.by_second)}")
        if rule.week_start != "MO":
            parts.append(f"WKST={rule.week_start}")
        return vRecur.from_ical(";".join(parts))

    @staticmethod
    def _add_attach(vevent: Event, attach: CalAttachment) -> None:
        """Add an ATTACH property for a CalAttachment (URI or binary)."""
        if attach.data is not None:
            bin_val = vBinary(attach.data)
            if attach.mime_type:
                bin_val.params["FMTTYPE"] = attach.mime_type
            vevent.add("attach", bin_val)
        elif attach.url:
            # URI attachment: use vText with encode=False to avoid URI escaping
            url_val = vText(attach.url)
            url_val.params.clear()
            if attach.mime_type:
                url_val.params["FMTTYPE"] = attach.mime_type
            vevent.add("attach", url_val, encode=False)
