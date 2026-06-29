"""Worker-side interface for the calendar module.

Mirrors ``InterfaceApiCalendarCalendar`` but for the Agent: no Flask context,
no HTTP response formatting. Reconstructs the User from its uid before
instantiating ``ModuleCalendar``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from app.auth.User import User
from app.config.init_config import init_get_user_domain_settings
from app.config.settings.DomainSettings import MailSettings, MailSettingsObj
from app.module.calendar.CalendarConst import (REMINDER_EMAIL_DEFAULT_TITLE,
                                               REMINDER_EMAIL_DEFAULT_WINDOW_MINUTES,
                                               REMINDER_EMAIL_LAST_RUN_KEY,
                                               REMINDER_EMAIL_LAST_RUN_TTL_SECONDS,
                                               REMINDER_EMAIL_LOOKAHEAD_MINUTES,
                                               REMINDER_EMAIL_SUBJECT_PREFIX,
                                               REMINDER_EMAIL_WHEN_LABEL,
                                               REMINDER_EMAIL_WHERE_LABEL)
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod
from app.module.mail.ModuleMailOutgoing import ModuleMailOutgoing
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.service import sogo_cache
from app.utils import constants as cs
from app.utils.datetime.DateTimeUtils import fmt_dt, parse_iso
from app.utils.exceptions import BugException
from app.utils.logger.logger import logger_agent

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.cache.ClientRedis import ClientRedis
    from app.module.calendar.model.CalEventReminder import CalEventReminder
    from app.module.calendar.model.CalSyncResult import CalSyncResult


class InterfaceAgentCalendar:
    """Calendar interface used by Agent tasks.

    Takes a ``user_uid`` (the only identity the broker carries) and resolves the full ``User`` plus
    the user-scoped domain settings before instantiating ``ModuleCalendar``. ``user_uid`` is ``None``
    for a system job (the periodic auto-sync sweep): no user is loaded and only the system-wide
    methods may be called.
    """

    def __init__(self, process_setting: ProcessSetting, user_uid: str | None) -> None:
        self._process_setting: ProcessSetting = process_setting
        self.user: User | None = self._load_user(process_setting, user_uid) if user_uid else None
        self.module: ModuleCalendar = ModuleCalendar(process_setting, cache=sogo_cache())

    def export_calendar(
        self, calendar_key: str,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
    ) -> str:
        """Return the VCALENDAR string for the given calendar.

        Storage of the result (memory or file) is the task's responsibility - this
        interface stays free of any persistence concern.

        :param calendar_key: key of the calendar to export.
        :type calendar_key: str
        :param date_start: lower bound of the export window; None means unbounded.
        :type date_start: datetime | None
        :param date_end: upper bound of the export window; None means unbounded.
        :type date_end: datetime | None
        :return: the serialised VCALENDAR text.
        :rtype: str
        """
        return self.module.serialize_to_ics(
            self._require_user(), calendar_key, date_start=date_start, date_end=date_end,
        )

    def import_calendar(self, calendar_key: str, ics_text: str) -> CalSyncResult:
        """Apply an ICS payload to the given calendar and return the import counters.

        :param calendar_key: key of the target calendar.
        :type calendar_key: str
        :param ics_text: VCALENDAR text to import.
        :type ics_text: str
        :return: the import counters.
        :rtype: CalSyncResult
        """
        return self.module.apply_import(self._require_user(), calendar_key, ics_text)

    def sync_external_calendar(self, calendar_key: str) -> CalSyncResult:
        """Fetch and mirror an external ICS calendar, returning the sync counters.

        :param calendar_key: key of the external calendar to sync.
        :type calendar_key: str
        :return: the sync counters.
        :rtype: CalSyncResult
        """
        return self.module.sync_external_calendar(self._require_user(), calendar_key)

    def sync_all_due_external(self) -> dict[str, int]:
        """System-wide auto-sync sweep (no user scope): sync every external calendar whose interval elapsed.

        Used by the periodic auto-sync job, which builds this interface with ``user_uid=None``; the sweep
        reads each calendar's owner from its row, so no acting user is needed.

        :return: aggregate counts ``{"total", "synced", "failed", "skipped"}``.
        :rtype: dict[str, int]
        """
        return self.module.sync_all_due_external()

    def send_due_email_reminders(self) -> dict[str, int]:
        """System-wide sweep (no user scope): email every reminder that became due since the last run.

        Reads the active email reminders across all users (the module already expands recurring events)
        and keeps those whose trigger lands in the dedup window ``(last_run, now]``; ``last_run`` is read
        from and written back to Redis so a reminder fires exactly once, even across restarts (first run
        defaults to one tick back). Reminders are grouped by owner: each owner's outgoing mail client is
        built from their domain settings and the message is sent best-effort - one failure never aborts
        the batch.

        :return: aggregate counts ``{"total", "sent", "failed"}``.
        """
        cache: ClientRedis = sogo_cache()
        now: datetime = datetime.now(timezone.utc)
        window_start: datetime = self._read_reminder_last_run(cache, now)

        # lookahead keeps reminders eligible just after their event ends, so a short event due in the
        # window is not dropped by the engine's "active" check; the dedup stays on trigger_at below.
        active: list[CalEventReminder] = self.module.get_reminders(
            None, method=ReminderMethod.EMAIL, lookahead_minutes=REMINDER_EMAIL_LOOKAHEAD_MINUTES,
        )
        reminders: list[CalEventReminder] = [
            reminder for reminder in active if window_start < reminder.trigger_at <= now
        ]
        counts: dict[str, int] = {"total": len(reminders), "sent": 0, "failed": 0}

        by_owner: dict[str, list[CalEventReminder]] = {}
        for reminder in reminders:
            if reminder.user_uid:
                by_owner.setdefault(reminder.user_uid, []).append(reminder)

        for owner_uid, owner_reminders in by_owner.items():
            try:
                user, domain_settings = self._load_user_with_settings(self._process_setting, owner_uid)
                mail_module: ModuleMailOutgoing = ModuleMailOutgoing(
                    user, MailSettingsObj(domain_settings[MailSettings.subparent]),
                )
            except Exception:  # pylint: disable=broad-exception-caught
                logger_agent.exception("Could not prepare outgoing mail for reminder owner %s", owner_uid)
                counts["failed"] += len(owner_reminders)
                continue
            for reminder in owner_reminders:
                try:
                    # TODO: once ModuleMailOutgoing exposes a system send (is_system=True / SMTP master
                    # credentials), use it - a worker has no user password, so today this relies on the
                    # domain relay accepting unauthenticated submission.
                    mail_module.send_mail(cs.DEFAULT_IDENTITY_KEY_VALUE, self._build_reminder_mail(user, reminder))
                    counts["sent"] += 1
                except Exception:  # pylint: disable=broad-exception-caught
                    logger_agent.exception(
                        "Failed to send email reminder for event %s to %s", reminder.event_key, owner_uid,
                    )
                    counts["failed"] += 1

        cache.set(REMINDER_EMAIL_LAST_RUN_KEY, now.isoformat(), ttl=REMINDER_EMAIL_LAST_RUN_TTL_SECONDS)
        return counts

    @staticmethod
    def _read_reminder_last_run(cache: ClientRedis, now: datetime) -> datetime:
        """Return the dedup watermark from Redis, or one default window back on the first run."""
        raw = cache.get(REMINDER_EMAIL_LAST_RUN_KEY, str)
        if isinstance(raw, str):
            parsed: datetime | None = parse_iso(raw)
            if parsed is not None:
                return parsed
        return now - timedelta(minutes=REMINDER_EMAIL_DEFAULT_WINDOW_MINUTES)

    @staticmethod
    def _build_reminder_mail(user: User, reminder: CalEventReminder) -> dict[str, Any]:
        """Build the plain-text reminder message for the outgoing mail module."""
        title: str = reminder.title or REMINDER_EMAIL_DEFAULT_TITLE
        lines: list[str] = [f"{REMINDER_EMAIL_SUBJECT_PREFIX}: {title}", ""]
        if reminder.date_start is not None:
            lines.append(f"{REMINDER_EMAIL_WHEN_LABEL}: {fmt_dt(reminder.date_start)}")
        if reminder.location:
            lines.append(f"{REMINDER_EMAIL_WHERE_LABEL}: {reminder.location}")
        return {
            "from_addr": user.mail,
            "to": [user.mail],
            "subject": f"{REMINDER_EMAIL_SUBJECT_PREFIX}: {title}",
            "body": "\n".join(lines),
            "is_html": False,
        }

    def _require_user(self) -> User:
        """Return the acting user, or raise if this interface was built for a system job (no user)."""
        if self.user is None:
            raise BugException("InterfaceAgentCalendar was built without a user (system mode)")
        return self.user

    @staticmethod
    def _load_user(process_setting: ProcessSetting, user_uid: str) -> User:
        """Rehydrate a User from its uid. Same shape as the Flask before_request gives."""
        user, _ = InterfaceAgentCalendar._load_user_with_settings(process_setting, user_uid)
        return user

    @staticmethod
    def _load_user_with_settings(process_setting: ProcessSetting, user_uid: str) -> tuple[User, dict]:
        """Rehydrate a User and return it with its resolved domain settings (loaded once)."""
        # pylint: disable=duplicate-code
        user: User = User(uid=user_uid)
        user.mail = user_uid
        user_domain_settings: dict = init_get_user_domain_settings(user)
        ModuleUserProfile(process_setting, user_domain_settings).get_user_profile(user)
        return user, user_domain_settings
