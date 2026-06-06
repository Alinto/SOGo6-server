"""Unit tests for JobCanceller - agent and persistency are mocked."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, call

from app.agent.jobs.JobCanceller import JobCanceller
from app.agent.jobs.JobState import JobState
from app.agent.jobs.JobStatus import JobStatus


def _state(status=JobStatus.STARTED) -> JobState:
    return JobState(
        job_id="t-1", name="example", status=status,
        user_uid="alice",
        date_planned=datetime(2026, 5, 28, 10, 0, 0, tzinfo=timezone.utc),
    )


def _canceller():
    agent_mock = MagicMock()
    persistency_mock = MagicMock()
    return JobCanceller(agent_mock, persistency_mock), agent_mock, persistency_mock


def test_cancel_does_nothing_when_task_unknown():
    canceller, agent_mock, persistency = _canceller()
    persistency.get.return_value = None
    canceller.cancel("missing")
    agent_mock.cancel.assert_not_called()


def test_cancel_does_nothing_when_already_terminal():
    canceller, agent_mock, persistency = _canceller()
    persistency.get.return_value = _state(status=JobStatus.SUCCESS)
    canceller.cancel("t-1")
    agent_mock.cancel.assert_not_called()


def test_cancel_sends_sigterm_then_returns_when_task_becomes_terminal():
    canceller, agent_mock, persistency = _canceller()
    # First read confirms the task is alive; second read inside the poll loop sees it terminal.
    persistency.get.side_effect = [_state(status=JobStatus.STARTED), _state(status=JobStatus.CANCELED)]
    canceller.cancel("t-1", soft_wait_seconds=1.0)
    agent_mock.cancel.assert_called_once_with("t-1", signal="SIGTERM")


def test_cancel_escalates_to_sigkill_when_grace_window_elapses():
    canceller, agent_mock, persistency = _canceller()
    persistency.get.return_value = _state(status=JobStatus.STARTED)  # never terminal
    canceller.cancel("t-1", soft_wait_seconds=0.05)
    calls = agent_mock.cancel.call_args_list
    assert calls[0] == call("t-1", signal="SIGTERM")
    assert calls[-1] == call("t-1", signal="SIGKILL")


def test_cancel_skips_sigkill_when_task_terminates_during_wait():
    canceller, agent_mock, persistency = _canceller()
    # Initial check + a few STARTED polls, then CANCELED before the deadline.
    persistency.get.side_effect = [
        _state(status=JobStatus.STARTED),  # initial
        _state(status=JobStatus.STARTED),  # poll 1
        _state(status=JobStatus.CANCELED), # poll 2 - exit
    ]
    canceller.cancel("t-1", soft_wait_seconds=5.0)
    sigkill = [c for c in agent_mock.cancel.call_args_list if c.kwargs.get("signal") == "SIGKILL"]
    assert sigkill == []
