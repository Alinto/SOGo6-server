"""Builds the configured ``JobLargeStore`` backend.

Lives outside the ABC and its subclasses so it can import the concrete backends
at module level (the subclasses import the ABC to inherit from it). Called once at
``Agent`` construction to pick the backend from ``SOGO_P_AGENT_LARGE_STORE``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.agent.jobs.job_large_store.JobLargeStorage import JobLargeStorage
from app.agent.jobs.job_large_store.JobLargeStore import JobLargeStore
from app.agent.jobs.job_large_store.JobLargeStoreFile import JobLargeStoreFile
from app.agent.jobs.job_large_store.JobLargeStoreInMemory import JobLargeStoreInMemory

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.cache.ClientRedis import ClientRedis


class JobLargeStoreBuilder:
    """Picks the large-blob backend from the process configuration."""

    @staticmethod
    def build(process_setting: ProcessSetting, cache: ClientRedis) -> JobLargeStore:
        """Return the backend selected by ``SOGO_P_AGENT_LARGE_STORE``.

        :param process_setting: process configuration carrying the backend choice.
        :type process_setting: ProcessSetting
        :param cache: Redis client injected into the in-memory backend.
        :type cache: ClientRedis
        :return: a ``JobLargeStoreFile`` or ``JobLargeStoreInMemory`` instance.
        :rtype: JobLargeStore
        :raises ValueError: the setting does not match a known backend.
        """
        if JobLargeStorage(process_setting.SOGO_P_AGENT_LARGE_STORE) == JobLargeStorage.FILE:
            return JobLargeStoreFile()
        return JobLargeStoreInMemory(cache)
