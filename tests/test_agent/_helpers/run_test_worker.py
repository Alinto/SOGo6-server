"""Worker entrypoint used by the e2e integration test.

Mirrors ``app.agent.run`` but registers TaskTest and skips Beat (no schedule file needed).
Run as ``python -m tests.test_agent._helpers.run_test_worker``.
"""
from __future__ import annotations

import os

from app.agent.Agent import agent
from app.agent.tasks.TaskRecovery import TaskRecovery
from app.config.init_config import init_infra
from app.service import set_cache
from tests.test_agent._helpers.TaskTest import TaskTest


def main() -> None:
    cache, persistency = init_infra()
    set_cache(cache)
    agent.register(TaskTest())
    agent.register_lifecycle_hooks(persistency)
    TaskRecovery(agent, persistency, cache).reconcile_orphans()
    argv: list[str] = [
        "worker", "-l", "INFO",
        "--pool=prefork", "--concurrency", "1",
        "--without-mingle", "--without-gossip", "--without-heartbeat",
    ]
    # pylint: disable=protected-access
    agent._celery.worker_main(argv)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
