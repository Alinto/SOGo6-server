"""Entrypoint for the SOGo Agent process: ``poetry run agent`` boots an Agent worker.

This module knows nothing about the underlying task framework — all configuration and
command-line construction live in ``AgentApp.start_worker``. It is also in charge of
wiring the runtime dependencies (cache singleton, TaskPersistency, lifecycle hooks).
"""
from __future__ import annotations

from app.agent.AgentApp import agent
from app.agent.tasks.TaskPersistency import TaskPersistency
from app.config.settings.ProcessSetting import process_config
from app.manager.cache.ClientRedis import ClientRedis
from app.service import set_cache, sogo_cache
from app.utils.logger.logger import logger


def main() -> None:
    """Start the Agent worker (with embedded Beat). Settings come from ``ProcessSetting``."""
    logger.info("Starting SOGo Agent")
    # Initialise the cache singleton, mirroring what app.run does for the Flask process,
    # so any code path (tasks, hooks, future modules) can call ``sogo_cache()`` uniformly.
    set_cache(ClientRedis(
        url_str=process_config.SOGO_P_REDIS_URL,
        resp3=process_config.SOGO_P_REDIS_RESP_3,
    ))
    persistency: TaskPersistency = TaskPersistency(
        sogo_cache(), ttl_seconds=process_config.SOGO_P_AGENT_TASK_STATE_TTL_SECONDS,
    )
    agent.register_lifecycle_hooks(persistency)
    agent.start_worker()


if __name__ == "__main__":
    main()
