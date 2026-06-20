"""Worker-side interface for the calendar module.

Mirrors ``InterfaceApiCalendarCalendar`` but for the Agent: no Flask context,
no HTTP response formatting. Reconstructs the User from its uid before
instantiating ``ModuleCalendar``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.auth.User import User
from app.config.init_config import init_get_user_domain_settings
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.service import sogo_cache

if TYPE_CHECKING:
    from datetime import datetime
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.module.calendar.model.CalSyncResult import CalSyncResult


class InterfaceAgentCalendar:
    """Calendar interface used by Agent tasks.

    Takes a ``user_uid`` (the only identity the broker carries) and resolves the
    full ``User`` plus the user-scoped domain settings before instantiating
    ``ModuleCalendar``.
    """

    def __init__(self, process_setting: ProcessSetting, user_uid: str) -> None:
        self._process_setting: ProcessSetting = process_setting
        self.user: User = self._load_user(process_setting, user_uid)
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
            self.user, calendar_key, date_start=date_start, date_end=date_end,
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
        return self.module.apply_import(self.user, calendar_key, ics_text)

    def sync_external_calendar(self, calendar_key: str) -> CalSyncResult:
        """Fetch and mirror an external ICS calendar, returning the sync counters.

        :param calendar_key: key of the external calendar to sync.
        :type calendar_key: str
        :return: the sync counters.
        :rtype: CalSyncResult
        """
        return self.module.sync_external_calendar(self.user, calendar_key)

    @staticmethod
    def _load_user(process_setting: ProcessSetting, user_uid: str) -> User:
        """Rehydrate a User from its uid. Same shape as the Flask before_request gives."""
        user: User = User(uid=user_uid)
        user.mail = user_uid
        user_domain_settings: dict = init_get_user_domain_settings(user)
        ModuleUserProfile(process_setting, user_domain_settings).get_user_profile(user)
        return user
