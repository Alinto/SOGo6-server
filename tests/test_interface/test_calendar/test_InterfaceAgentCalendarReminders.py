"""Unit tests for InterfaceAgentCalendar.send_due_email_reminders (periodic email-reminder sweep)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.config.settings.DomainSettings import MailSettings
from app.interface.calendar.InterfaceAgentCalendar import InterfaceAgentCalendar
from app.module.calendar.model.CalEventReminder import CalEventReminder
from app.module.calendar.model.enums.ReminderMethod import ReminderMethod

_IFACE = "app.interface.calendar.InterfaceAgentCalendar"


def _rem(user_uid, key):
    # trigger just before "now" so it lands inside the sweep's (last_run, now] firing window.
    now = datetime.now(timezone.utc)
    return CalEventReminder(
        event_key=key, title="Standup", location=None,
        date_start=now + timedelta(minutes=10),
        date_end=None, timezone=None, calendar_timezone=None,
        method=ReminderMethod.EMAIL, minutes_before=10,
        trigger_at=now - timedelta(seconds=1),
        user_uid=user_uid,
    )


def _build_interface(reminders):
    interface = object.__new__(InterfaceAgentCalendar)
    interface._process_setting = MagicMock()
    interface.module = MagicMock()
    interface.module.get_reminders.return_value = reminders
    return interface


def _patches(mail):
    cache = MagicMock()
    cache.get.return_value = None
    user = MagicMock()
    user.mail = "a@example.com"
    return (cache,
            patch(f"{_IFACE}.sogo_cache", return_value=cache),
            patch(f"{_IFACE}.ModuleMailOutgoing", return_value=mail),
            patch(f"{_IFACE}.MailSettingsObj"),
            patch.object(InterfaceAgentCalendar, "_load_user_with_settings",
                         side_effect=lambda ps, uid: (user, {MailSettings.subparent: {}})))


def test_send_groups_by_owner_and_writes_watermark():
    interface = _build_interface([_rem("a@x", "e1"), _rem("a@x", "e2"), _rem("b@x", "e3")])
    mail = MagicMock()
    cache, p_cache, p_mail, p_settings, p_user = _patches(mail)
    with p_cache, p_mail, p_settings, p_user:
        counts = interface.send_due_email_reminders()
    assert counts == {"total": 3, "sent": 3, "failed": 0}
    assert mail.send_mail.call_count == 3
    cache.set.assert_called_once()  # last-run watermark written


def test_send_continues_on_failure():
    interface = _build_interface([_rem("a@x", "e1"), _rem("a@x", "e2")])
    mail = MagicMock()
    mail.send_mail.side_effect = [RuntimeError("smtp down"), None]
    cache, p_cache, p_mail, p_settings, p_user = _patches(mail)
    with p_cache, p_mail, p_settings, p_user:
        counts = interface.send_due_email_reminders()
    assert counts == {"total": 2, "sent": 1, "failed": 1}
