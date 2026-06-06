"""Agent large-store registration + the not-registered guard."""
from unittest.mock import MagicMock

import pytest

from app.agent.Agent import Agent
from app.agent.jobs.job_large_store.JobLargeStoreFile import JobLargeStoreFile
from app.config.settings.ProcessSetting import process_config
from app.utils.exceptions import AggravatedException


def test_get_large_store_raises_a_controlled_error_before_registration():
    a = Agent(process_config)
    with pytest.raises(AggravatedException):
        a.get_large_store()


def test_register_then_get_returns_the_built_store():
    a = Agent(process_config)
    a.register_large_store(MagicMock())  # default backend is FILE -> no real cache use
    assert isinstance(a.get_large_store(), JobLargeStoreFile)
