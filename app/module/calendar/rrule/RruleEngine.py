from __future__ import annotations

import dataclasses
from calendar import isleap as _isleap  # pylint: disable=no-name-in-module
from calendar import monthrange as _monthrange  # pylint: disable=no-name-in-module
from datetime import date as _date
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.module.calendar.CalendarConst import MAX_RRULE_EXPANSION_YEARS
from app.module.calendar.model.enums.RecurrenceFrequency import RecurrenceFrequency
from app.utils.datetime.DateTimeUtils import to_utc
from app.utils.logger.logger import logger_calendar

if TYPE_CHECKING:
    from app.module.calendar.model.CalEvent import CalEvent
    from app.module.calendar.model.CalRecurrenceRule import CalRecurrenceRule

# Cap to avoid runaway expansion (daily occurrences over the maximum expansion window)
_MAX_OCCURRENCES: int = 365 * MAX_RRULE_EXPANSION_YEARS

_WEEKDAY_MAP: dict[str, int] = {
    "MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6,
}
_WEEKDAY_COUNT = len(_WEEKDAY_MAP.keys())


class RruleEngine:
    """
    Expands a recurring CalEvent into individual occurrences within a UTC date range.

    Supports all FREQ values, INTERVAL, UNTIL, COUNT, BYDAY (with positional prefixes),
    BYMONTHDAY, BYMONTH, BYYEARDAY, BYWEEKNO, BYSETPOS, BYHOUR, BYMINUTE, BYSECOND,
    EXDATE, RDATE and RECURRENCE-ID overrides.

    RFC 5545 §3.3.10 - Recurrence Rule
    """

    # Public interface

    def expand(
        self,
        master: CalEvent,
        start: datetime,
        end: datetime,
        overrides: list[CalEvent] | None = None,
    ) -> list[CalEvent]:
        """Expand master into occurrences overlapping [start, end].

        RFC 5545 §3.3.10 (expansion algorithm), §3.8.4.4 (RECURRENCE-ID overrides),
        §3.8.5.1 (EXDATE filtering).

        Returns [master] unchanged if it has no recurrence_rule.
        Each generated occurrence is a copy of master with updated start/end
        and recurrence_id set to the occurrence start.
        """
        if master.recurrence_rule is None:
            return [master]

        rule: CalRecurrenceRule = master.recurrence_rule
        duration: timedelta = master.duration

        override_map: dict[datetime, CalEvent] = {}
        if overrides:
            for ov in overrides:
                if ov.recurrence_id is not None:
                    override_map[self._normalize_dt(ov.recurrence_id)] = ov

        occurrence_starts: list[datetime] = self._generate_dates(rule, master.require_date_start, end)

        result: list[CalEvent] = []
        for occ_start in occurrence_starts:
            # A task with no due date has no end, so every occurrence stays open-ended.
            occ_end: datetime | None = occ_start + duration if master.date_end is not None else None

            if occ_end is not None and occ_end < start:
                continue

            occ_key: datetime = self._normalize_dt(occ_start)
            if occ_key in override_map:
                # RFC 5545 §3.8.4.4: a RECURRENCE-ID override replaces the slot,
                # even if the slot is also listed in EXDATE.
                override_event: CalEvent = override_map[occ_key]
                # A task override with no due date has no end, so it always overlaps the lower bound.
                if (
                    override_event.date_end is None or override_event.date_end >= start
                ) and override_event.require_date_start <= end:
                    result.append(override_event)
            elif self._is_excluded(occ_start, master.recurrence_exceptions):
                continue
            else:
                result.append(self._make_occurrence(master, occ_start, occ_end))

        return result

    def get_min_date(self, master: CalEvent) -> datetime:
        """Return the start of the first occurrence - always dtstart.

        RFC 5545 §3.3.10 - The recurrence set starts at DTSTART.
        """
        return master.require_date_start

    def get_max_date(self, master: CalEvent) -> datetime | None:
        """Return the end of the last occurrence, or None for an unbounded series.

        RFC 5545 §3.3.10 - UNTIL and COUNT bound the series.
        Returns None when neither is set (the recurrence extends indefinitely).
        For non-recurring events, returns date_end directly.

        Note: this method computes the actual last occurrence, not just UNTIL.
        For example, WEEKLY;BYDAY=MO;UNTIL=Thursday will return the Monday before
        Thursday, not Thursday itself.
        """
        rule: CalRecurrenceRule | None = master.recurrence_rule
        if rule is None:
            return master.date_end
        if rule.until is None and rule.count is None:
            return None
        # When only COUNT is set, cap the search window to a hard bound so an unbounded
        # _generate_dates call cannot run away - COUNT will normally stop earlier.
        hard_limit: datetime = master.require_date_start + timedelta(days=365 * MAX_RRULE_EXPANSION_YEARS)
        limit: datetime = rule.until if rule.until is not None else hard_limit
        dates: list[datetime] = self._generate_dates(rule, master.require_date_start, limit)
        if not dates:
            return master.date_end
        return dates[-1] + master.duration

    # Date generation

    def _generate_dates(
        self,
        rule: CalRecurrenceRule,
        dtstart: datetime,
        limit: datetime,
    ) -> list[datetime]:
        """Generate all candidate occurrence datetimes from dtstart up to min(UNTIL, limit).

        RFC 5545 §3.3.10 - FREQ dispatch, UNTIL, COUNT, INTERVAL;
        §3.8.5.2 - RDATE: additional dates appended after FREQ expansion.
        """
        until: datetime = rule.until if rule.until and rule.until < limit else limit

        freq: RecurrenceFrequency = rule.frequency
        if freq == RecurrenceFrequency.SECONDLY:
            dates: list[datetime] = self._gen_sub_daily(rule, dtstart, until, timedelta(seconds=rule.interval))
        elif freq == RecurrenceFrequency.MINUTELY:
            dates = self._gen_sub_daily(rule, dtstart, until, timedelta(minutes=rule.interval))
        elif freq == RecurrenceFrequency.HOURLY:
            dates = self._gen_sub_daily(rule, dtstart, until, timedelta(hours=rule.interval))
        elif freq == RecurrenceFrequency.DAILY:
            dates = self._gen_daily(rule, dtstart, until)
        elif freq == RecurrenceFrequency.WEEKLY:
            dates = self._gen_weekly(rule, dtstart, until)
        elif freq == RecurrenceFrequency.MONTHLY:
            dates = self._gen_monthly(rule, dtstart, until)
        elif freq == RecurrenceFrequency.YEARLY:
            dates = self._gen_yearly(rule, dtstart, until)
        else:
            logger_calendar.warning("RruleEngine: unknown FREQ=%s - expansion skipped", freq)
            dates = []

        # RFC 5545 §3.8.5.2 - RDATE
        for rdate in rule.additional_dates:
            rdate_utc: datetime = self._normalize_dt(rdate)
            if dtstart <= rdate_utc <= limit and rdate_utc not in dates:
                dates.append(rdate_utc)

        dates.sort()
        return dates

    def _gen_sub_daily(
        self,
        rule: CalRecurrenceRule,
        dtstart: datetime,
        until: datetime,
        step: timedelta,
    ) -> list[datetime]:
        """Common generator for SECONDLY, MINUTELY and HOURLY - applies BY* as filters.

        RFC 5545 §3.3.10 - SECONDLY, MINUTELY, HOURLY frequencies.
        BY* rules (BYDAY, BYMONTH, BYMONTHDAY, BYYEARDAY, BYWEEKNO,
        BYHOUR, BYMINUTE, BYSECOND) act as filters on the generated set.
        """
        dates: list[datetime] = []
        current: datetime = dtstart
        target_days: set[int] | None = self._parse_byday_names(rule.by_day) if rule.by_day else None

        while current <= until and len(dates) < _MAX_OCCURRENCES:
            passes: bool = True
            if target_days is not None and current.weekday() not in target_days:
                passes = False
            if rule.by_month and current.month not in rule.by_month:
                passes = False
            if rule.by_month_day and not self._matches_bymonthday(current, rule.by_month_day):
                passes = False
            if rule.by_year_day and not self._matches_byyearday(current, rule.by_year_day):
                passes = False
            if rule.by_week_no and not self._matches_byweekno(current, rule.by_week_no):
                passes = False
            if rule.by_hour and current.hour not in rule.by_hour:
                passes = False
            if rule.by_minute and current.minute not in rule.by_minute:
                passes = False
            if rule.by_second and current.second not in rule.by_second:
                passes = False
            if passes:
                dates.append(current)
                if rule.count is not None and len(dates) >= rule.count:
                    break
            current += step

        return dates

    def _gen_daily(  # pylint: disable=too-many-branches
        self,
        rule: CalRecurrenceRule,
        dtstart: datetime,
        until: datetime,
    ) -> list[datetime]:
        """RFC 5545 §3.3.10 - DAILY frequency.

        BYHOUR/BYMINUTE/BYSECOND expand each day into multiple occurrences.
        BYSETPOS selects within the day's set of matches.
        Other BY* rules (BYDAY, BYMONTH, BYMONTHDAY, BYYEARDAY, BYWEEKNO) act as filters.
        """
        dates: list[datetime] = []
        hours: list[int] = rule.by_hour or [dtstart.hour]
        minutes: list[int] = rule.by_minute or [dtstart.minute]
        seconds: list[int] = rule.by_second or [dtstart.second]
        target_days: set[int] | None = self._parse_byday_names(rule.by_day) if rule.by_day else None

        # Anchor to midnight so time expansion can generate times earlier than dtstart's time
        current: datetime = dtstart.replace(hour=0, minute=0, second=0, microsecond=0)

        while current <= until and len(dates) < _MAX_OCCURRENCES:
            day_matches: list[datetime] = []
            for h in hours:
                for m in minutes:
                    for s in seconds:
                        c: datetime = current.replace(hour=h, minute=m, second=s)
                        if c < dtstart or c > until:
                            continue
                        if target_days is not None and c.weekday() not in target_days:
                            continue
                        if rule.by_month and c.month not in rule.by_month:
                            continue
                        if rule.by_month_day and not self._matches_bymonthday(c, rule.by_month_day):
                            continue
                        if rule.by_year_day and not self._matches_byyearday(c, rule.by_year_day):
                            continue
                        if rule.by_week_no and not self._matches_byweekno(c, rule.by_week_no):
                            continue
                        day_matches.append(c)

            if rule.by_set_pos and day_matches:
                day_matches = self._apply_bysetpos(sorted(day_matches), rule.by_set_pos)

            for c in sorted(day_matches):
                dates.append(c)
                if rule.count is not None and len(dates) >= rule.count:
                    return dates

            current += timedelta(days=rule.interval)

        return dates

    def _gen_weekly(  # pylint: disable=too-many-branches,too-many-locals,too-many-nested-blocks
        self,
        rule: CalRecurrenceRule,
        dtstart: datetime,
        until: datetime,
    ) -> list[datetime]:
        """RFC 5545 §3.3.10 - WEEKLY frequency.

        BYDAY specifies which weekdays recur within the week.
        WKST defines the first day of the week (default MO), which determines
        week boundaries when INTERVAL > 1.
        BYSETPOS selects within the week's set of matches.
        """
        dates: list[datetime] = []
        hours: list[int] = rule.by_hour or [dtstart.hour]
        minutes: list[int] = rule.by_minute or [dtstart.minute]
        seconds: list[int] = rule.by_second or [dtstart.second]

        if not rule.by_day:
            current: datetime = dtstart.replace(hour=0, minute=0, second=0, microsecond=0)
            while current <= until and len(dates) < _MAX_OCCURRENCES:
                week_matches: list[datetime] = []
                for h in hours:
                    for m in minutes:
                        for s in seconds:
                            c: datetime = current.replace(hour=h, minute=m, second=s)
                            if c < dtstart or c > until:
                                continue
                            if rule.by_year_day and not self._matches_byyearday(c, rule.by_year_day):
                                continue
                            week_matches.append(c)
                if rule.by_set_pos and week_matches:
                    week_matches = self._apply_bysetpos(sorted(week_matches), rule.by_set_pos)
                for c in sorted(week_matches):
                    dates.append(c)
                    if rule.count is not None and len(dates) >= rule.count:
                        return dates
                current += timedelta(weeks=rule.interval)
            return dates

        target_days: set[int] = self._parse_byday_names(rule.by_day)
        wk_start_wd: int = _WEEKDAY_MAP.get(rule.week_start, 0)
        days_back: int = (dtstart.weekday() - wk_start_wd) % _WEEKDAY_COUNT
        week_cursor: datetime = (dtstart - timedelta(days=days_back)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        while week_cursor <= until and len(dates) < _MAX_OCCURRENCES:
            week_matches = []
            for day_off in range(_WEEKDAY_COUNT):
                day_base: datetime = week_cursor + timedelta(days=day_off)
                if day_base.weekday() not in target_days:
                    continue
                for h in hours:
                    for m in minutes:
                        for s in seconds:
                            c = day_base.replace(hour=h, minute=m, second=s)
                            if c < dtstart or c > until:
                                continue
                            if rule.by_month and c.month not in rule.by_month:
                                continue
                            if rule.by_year_day and not self._matches_byyearday(c, rule.by_year_day):
                                continue
                            week_matches.append(c)

            if rule.by_set_pos and week_matches:
                week_matches = self._apply_bysetpos(sorted(week_matches), rule.by_set_pos)

            for c in sorted(week_matches):
                dates.append(c)
                if rule.count is not None and len(dates) >= rule.count:
                    return dates

            week_cursor += timedelta(weeks=rule.interval)

        return dates

    def _gen_monthly(
        self,
        rule: CalRecurrenceRule,
        dtstart: datetime,
        until: datetime,
    ) -> list[datetime]:
        """RFC 5545 §3.3.10 - MONTHLY frequency.

        BYMONTHDAY and BYDAY (with optional positional prefix) determine which
        days of the month match. BYHOUR/BYMINUTE/BYSECOND further expand by time.
        BYSETPOS selects within the month's set of matches.
        """
        dates: list[datetime] = []
        month_cursor: datetime = dtstart.replace(day=1)

        while month_cursor <= until and len(dates) < _MAX_OCCURRENCES:
            if not rule.by_month or month_cursor.month in rule.by_month:
                matches: list[datetime] = self._month_matches(rule, month_cursor, dtstart)
                matches = self._expand_by_time(matches, rule, dtstart)
                if rule.by_set_pos and matches:
                    matches = self._apply_bysetpos(sorted(matches), rule.by_set_pos)
                for c in sorted(matches):
                    if c < dtstart or c > until:
                        continue
                    if rule.by_year_day and not self._matches_byyearday(c, rule.by_year_day):
                        continue
                    dates.append(c)
                    if rule.count is not None and len(dates) >= rule.count:
                        return dates
            month_cursor = self._add_months(month_cursor, rule.interval)

        return dates

    def _month_matches(
        self,
        rule: CalRecurrenceRule,
        month_base: datetime,
        dtstart: datetime,
    ) -> list[datetime]:
        """Datetimes within month_base's month that match BYMONTHDAY or BYDAY.

        RFC 5545 §3.3.10 - BYMONTHDAY (positive and negative values),
        BYDAY with and without positional prefix.
        """
        year: int = month_base.year
        month: int = month_base.month
        days_in_month: int = _monthrange(year, month)[1]

        if rule.by_month_day:
            matches: list[datetime] = []
            for mday in rule.by_month_day:
                actual: int = mday if mday > 0 else days_in_month + mday + 1
                if 1 <= actual <= days_in_month:
                    try:
                        matches.append(month_base.replace(day=actual))
                    except ValueError:
                        pass
            return matches

        if rule.by_day:
            matches = []
            for day_str in rule.by_day:
                position: int | None
                wd: int | None
                position, wd = self._parse_byday_entry(day_str)
                if wd is None:
                    continue
                if position is not None:
                    c: datetime | None = self._nth_weekday_in_month(month_base, wd, position, dtstart)
                    if c is not None:
                        matches.append(c)
                else:
                    matches.extend(self._all_weekdays_in_month(month_base, wd, dtstart))
            return matches

        if dtstart.day <= days_in_month:
            return [month_base.replace(day=dtstart.day)]
        return []

    def _gen_yearly(
        self,
        rule: CalRecurrenceRule,
        dtstart: datetime,
        until: datetime,
    ) -> list[datetime]:
        """RFC 5545 §3.3.10 - YEARLY frequency.

        Matching priority: BYWEEKNO > BYYEARDAY > default (BYMONTH + BYMONTHDAY/BYDAY).
        BYHOUR/BYMINUTE/BYSECOND expand matches by time after day-level selection.
        BYSETPOS selects within the year's set of matches.
        """
        dates: list[datetime] = []
        year: int = dtstart.year

        while year <= until.year and len(dates) < _MAX_OCCURRENCES:
            if rule.by_week_no:
                year_matches: list[datetime] = self._year_matches_byweekno(rule, year, dtstart)
            elif rule.by_year_day:
                year_matches = self._year_matches_byyearday(rule, year, dtstart)
            else:
                year_matches = self._year_matches_default(rule, year, dtstart)

            year_matches = self._expand_by_time(year_matches, rule, dtstart)
            if rule.by_set_pos and year_matches:
                year_matches = self._apply_bysetpos(sorted(year_matches), rule.by_set_pos)

            for c in sorted(year_matches):
                if c < dtstart or c > until:
                    continue
                dates.append(c)
                if rule.count is not None and len(dates) >= rule.count:
                    return dates

            year += rule.interval

        return dates

    def _year_matches_byweekno(
        self,
        rule: CalRecurrenceRule,
        year: int,
        dtstart: datetime,
    ) -> list[datetime]:
        """Datetimes matching BYWEEKNO + optional BYDAY for a given year.

        RFC 5545 §3.3.10 - BYWEEKNO: ordinal week numbers per ISO 8601
        (week starting Monday, week 1 contains the first Thursday of the year).
        """
        target_weekdays: set[int] = self._parse_byday_names(rule.by_day) if rule.by_day else {dtstart.weekday()}
        matches: list[datetime] = []
        assert rule.by_week_no is not None
        for week_no in rule.by_week_no:
            for wd in target_weekdays:
                iso_day: int = wd + 1  # ISO: 1=Mon ... 7=Sun
                try:
                    d: _date = _date.fromisocalendar(year, week_no, iso_day)
                    matches.append(datetime(
                        d.year, d.month, d.day,
                        dtstart.hour, dtstart.minute, dtstart.second,
                        tzinfo=dtstart.tzinfo,
                    ))
                except ValueError:
                    pass  # week_no does not exist in this year (e.g. week 53)
        return matches

    def _year_matches_byyearday(
        self,
        rule: CalRecurrenceRule,
        year: int,
        dtstart: datetime,
    ) -> list[datetime]:
        """Datetimes matching BYYEARDAY + optional BYDAY / BYMONTH filters for a given year.

        RFC 5545 §3.3.10 - BYYEARDAY: valid values +1..+366 and -366..-1;
        negative values count from the last day of the year.
        """
        target_weekdays: set[int] | None = self._parse_byday_names(rule.by_day) if rule.by_day else None
        n: int = self._days_in_year(year)
        matches: list[datetime] = []
        assert rule.by_year_day is not None
        for yd in rule.by_year_day:
            actual: int = yd if yd > 0 else n + yd + 1
            if not 1 <= actual <= n:
                continue
            try:
                d: _date = _date(year, 1, 1) + timedelta(days=actual - 1)
                match: datetime = datetime(
                    d.year, d.month, d.day,
                    dtstart.hour, dtstart.minute, dtstart.second,
                    tzinfo=dtstart.tzinfo,
                )
            except ValueError:
                continue
            if target_weekdays is not None and match.weekday() not in target_weekdays:
                continue
            if rule.by_month and match.month not in rule.by_month:
                continue
            matches.append(match)
        return matches

    def _year_matches_default(
        self,
        rule: CalRecurrenceRule,
        year: int,
        dtstart: datetime,
    ) -> list[datetime]:
        """Datetimes matching BYMONTH + BYMONTHDAY / BYDAY for a given year, or same date as dtstart.

        RFC 5545 §3.3.10 - YEARLY with BYMONTH, BYMONTHDAY, BYDAY;
        falls back to the same month/day as dtstart when no BY* rules are set.
        """
        target_months: list[int] = rule.by_month if rule.by_month else [dtstart.month]
        matches: list[datetime] = []
        for month in target_months:
            try:
                month_base: datetime = dtstart.replace(year=year, month=month, day=1)
            except ValueError:
                continue
            if rule.by_month_day or rule.by_day:
                matches.extend(self._month_matches(rule, month_base, dtstart))
            else:
                try:
                    matches.append(dtstart.replace(year=year, month=month))
                except ValueError:
                    pass
        return matches

    # Helpers

    @staticmethod
    def _normalize_dt(dt: datetime) -> datetime:
        # RFC 5545 §3.3.5 - DATE-TIME: all comparisons use UTC-aware datetimes
        return to_utc(dt)

    @staticmethod
    def _is_excluded(occ: datetime, exceptions: list[datetime]) -> bool:
        # RFC 5545 §3.8.5.1 - EXDATE: occurrence matches an exception date-time
        occ_utc: datetime = RruleEngine._normalize_dt(occ)
        return any(RruleEngine._normalize_dt(exc) == occ_utc for exc in exceptions)

    @staticmethod
    def _make_occurrence(master: CalEvent, start: datetime, end: datetime | None) -> CalEvent:
        # RFC 5545 §3.8.4.4 - RECURRENCE-ID: each generated occurrence carries the
        # original occurrence datetime as its recurrence identifier
        return dataclasses.replace(
            master,
            date_start=start,
            date_end=end,
            recurrence_id=start,
            recurrence_exceptions=[],
        )

    @staticmethod
    def _add_months(dt: datetime, n: int) -> datetime:
        """Advance by n months, clamping day to last valid day of the target month.

        RFC 5545 §3.3.10 - MONTHLY frequency: when the day exceeds the month length,
        it is clamped to the last day of the month.
        """
        total: int = (dt.year * 12 + dt.month - 1) + n
        year: int
        month_idx: int
        year, month_idx = divmod(total, 12)
        month: int = month_idx + 1
        max_day: int = _monthrange(year, month)[1]
        return dt.replace(year=year, month=month, day=min(dt.day, max_day))

    @staticmethod
    def _days_in_year(year: int) -> int:
        # RFC 5545 §3.3.10 - BYYEARDAY: leap year has 366 days
        return 366 if _isleap(year) else 365

    @staticmethod
    def _day_of_year(dt: datetime) -> int:
        # RFC 5545 §3.3.10 - BYYEARDAY: 1-based day-of-year index
        return dt.timetuple().tm_yday

    @staticmethod
    def _matches_bymonthday(dt: datetime, by_month_day: list[int]) -> bool:
        # RFC 5545 §3.3.10 - BYMONTHDAY: valid values +1..+31 and -31..-1
        # Negative values count backwards from the last day of the month
        days_in_month: int = _monthrange(dt.year, dt.month)[1]
        for mday in by_month_day:
            actual: int = mday if mday > 0 else days_in_month + mday + 1
            if dt.day == actual:
                return True
        return False

    @staticmethod
    def _matches_byyearday(dt: datetime, by_year_day: list[int]) -> bool:
        # RFC 5545 §3.3.10 - BYYEARDAY: valid values +1..+366 and -366..-1
        # Negative values count backwards from the last day of the year
        doy: int = RruleEngine._day_of_year(dt)
        n: int = RruleEngine._days_in_year(dt.year)
        for yd in by_year_day:
            actual: int = yd if yd > 0 else n + yd + 1
            if doy == actual:
                return True
        return False

    @staticmethod
    def _matches_byweekno(dt: datetime, by_week_no: list[int]) -> bool:
        # RFC 5545 §3.3.10 - BYWEEKNO: week numbering per ISO 8601
        _, week, _ = dt.isocalendar()
        return week in by_week_no

    @staticmethod
    def _parse_byday_entry(s: str) -> tuple[int | None, int | None]:
        """Parse a BYDAY entry like 'MO', '1MO' or '-1FR' into (position, weekday_int).

        RFC 5545 §3.3.10 - BYDAY: an optional signed integer prefix specifies the
        nth occurrence of that weekday within the month (MONTHLY) or year (YEARLY).
        """
        day_name: str = s[-2:].upper()
        wd: int | None = _WEEKDAY_MAP.get(day_name)
        if wd is None:
            return None, None
        prefix: str = s[:-2]
        position: int | None = int(prefix) if prefix else None
        return position, wd

    @staticmethod
    def _parse_byday_names(by_day: list[str]) -> set[int]:
        """Extract weekday integers from BYDAY entries, ignoring positional prefixes.

        RFC 5545 §3.3.10 - BYDAY
        """
        result: set[int] = set()
        for s in by_day:
            _, wd = RruleEngine._parse_byday_entry(s)
            if wd is not None:
                result.add(wd)
        return result

    @staticmethod
    def _nth_weekday_in_month(base: datetime, weekday: int, n: int, dtstart: datetime) -> datetime | None:
        """Return the nth occurrence (1=first, -1=last) of weekday in base's month, or None if out of range.

        RFC 5545 §3.3.10 - BYDAY with positional prefix in MONTHLY context
        """
        year: int = base.year
        month: int = base.month
        all_days: list[datetime] = []
        for day in range(1, _monthrange(year, month)[1] + 1):
            try:
                c: datetime = datetime(
                    year, month, day,
                    dtstart.hour, dtstart.minute, dtstart.second,
                    tzinfo=dtstart.tzinfo,
                )
            except ValueError:
                continue
            if c.weekday() == weekday:
                all_days.append(c)
        if not all_days:
            return None
        if 0 < n <= len(all_days):
            return all_days[n - 1]
        if n < 0 and abs(n) <= len(all_days):
            return all_days[n]
        return None

    @staticmethod
    def _all_weekdays_in_month(base: datetime, weekday: int, dtstart: datetime) -> list[datetime]:
        """Return all occurrences of weekday in base's month, preserving dtstart's time.

        RFC 5545 §3.3.10 - BYDAY without positional prefix in MONTHLY context
        """
        year: int = base.year
        month: int = base.month
        result: list[datetime] = []
        for day in range(1, _monthrange(year, month)[1] + 1):
            try:
                c: datetime = datetime(
                    year, month, day,
                    dtstart.hour, dtstart.minute, dtstart.second,
                    tzinfo=dtstart.tzinfo,
                )
            except ValueError:
                continue
            if c.weekday() == weekday:
                result.append(c)
        return result

    @staticmethod
    def _expand_by_time(matches: list[datetime], rule: CalRecurrenceRule, dtstart: datetime) -> list[datetime]:
        """Expand each match by BYHOURxBYMINUTExBYSECOND when any of these are set.

        RFC 5545 §3.3.10 - BYHOUR, BYMINUTE, BYSECOND: for frequencies coarser than
        the component (e.g. DAILY+BYHOUR), each period generates one occurrence per
        combination of the specified values.
        """
        if not rule.by_hour and not rule.by_minute and not rule.by_second:
            return matches
        hours: list[int] = rule.by_hour or [dtstart.hour]
        minutes: list[int] = rule.by_minute or [dtstart.minute]
        seconds: list[int] = rule.by_second or [dtstart.second]
        result: list[datetime] = []
        for dt in matches:
            for h in hours:
                for m in minutes:
                    for s in seconds:
                        result.append(dt.replace(hour=h, minute=m, second=s))
        return result

    @staticmethod
    def _apply_bysetpos(matches: list[datetime], by_set_pos: list[int]) -> list[datetime]:
        """Select specific positions from a set of matches.

        RFC 5545 §3.3.10 - BYSETPOS: applies to the complete set of recurrence
        instances generated by the BY* rules for a given recurrence period.
        Positive values count from the start, negative from the end.
        """
        n: int = len(matches)
        result: list[datetime] = []
        for pos in by_set_pos:
            if 1 <= pos <= n:
                result.append(matches[pos - 1])
            elif -n <= pos <= -1:
                result.append(matches[pos])
        return result
