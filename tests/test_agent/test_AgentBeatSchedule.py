"""Beat schedule built from each job's ``cron`` declaration."""
from typing import Any

import pytest

from app.agent.Agent import Agent
from app.agent.jobs.Job import Job
from app.agent.jobs.JobRequest import JobRequest
from app.config.settings.ProcessSetting import process_config
from app.module.admin.jobs.JobCleanupLargeStore import JobCleanupLargeStore
from app.module.calendar.jobs.JobExportIcs import JobExportIcs
from app.utils.exceptions import AggravatedException


class _NarrowRetryRequest(JobRequest):
    name = "test.retry.narrow"
    retry_for = (ValueError,)

    def payload(self):
        return {}


class _NarrowRetryJob(Job):
    request_class = _NarrowRetryRequest

    def process(self, payload: dict[str, Any], *, user_uid, job_id):
        return {}


def test_crontab_from_string_maps_the_five_fields():
    ct = Agent._crontab_from_string("0 2 * * *")
    assert "0 2 * * *" in repr(ct)


def test_crontab_from_string_rejects_a_wrong_field_count():
    with pytest.raises(AggravatedException):
        Agent._crontab_from_string("0 2 * *")


def test_crontab_from_string_rejects_an_out_of_range_field():
    with pytest.raises(AggravatedException):
        Agent._crontab_from_string("0 99 * * *")


def test_build_schedule_has_an_entry_for_a_request_declaring_cron():
    agent = Agent(process_config)
    agent.register_job_handler(JobCleanupLargeStore())
    schedule = agent._build_beat_schedule()
    request_class = JobCleanupLargeStore.request_class
    entry = schedule[request_class.name]
    assert entry["task"] == request_class.name
    assert entry["kwargs"]["schedule_name"] == request_class.name
    assert request_class.cron in repr(entry["schedule"])


def test_on_demand_job_without_cron_is_not_scheduled():
    # Export ICS is enqueued on demand (cron is None) -> never in the beat schedule,
    # even though it is a registered handler.
    agent = Agent(process_config)
    agent.register_job_handler(JobExportIcs())
    assert JobExportIcs.request_class.cron is None
    assert JobExportIcs.request_class.name not in agent._build_beat_schedule()


def test_request_retry_for_is_applied_to_the_celery_task():
    agent = Agent(process_config)
    agent.register_job_handler(_NarrowRetryJob())
    task = agent._celery.tasks["test.retry.narrow"]
    assert task.autoretry_for == (ValueError,)
