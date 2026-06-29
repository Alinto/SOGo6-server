"""Unit tests for the JobSendEmailReminders periodic Agent job (calendar module)."""
from unittest.mock import MagicMock, patch

from app.module.calendar.jobs.JobSendEmailReminders import JobSendEmailReminders, JobRequestSendEmailReminders

_JOB_MODULE = "app.module.calendar.jobs.JobSendEmailReminders"


def test_request_metadata():
    assert JobSendEmailReminders.request_class is JobRequestSendEmailReminders
    assert JobRequestSendEmailReminders.name == "calendar.reminder.email"
    assert JobRequestSendEmailReminders.cron == "* * * * *"
    assert JobRequestSendEmailReminders().payload() == {}


def test_process_delegates_to_the_interface_sweep():
    inter = MagicMock()
    inter.send_due_email_reminders.return_value = {"total": 2, "sent": 2, "failed": 0}
    with patch(f"{_JOB_MODULE}.InterfaceAgentCalendar", return_value=inter) as inter_cls:
        result = JobSendEmailReminders().process({}, user_uid=None, job_id="j-1")
    assert inter_cls.call_args.args[1] is None  # system job (user_uid=None)
    inter.send_due_email_reminders.assert_called_once()
    assert result == {"total": 2, "sent": 2, "failed": 0}
