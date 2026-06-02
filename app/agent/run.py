"""``poetry run agent`` entrypoint."""
from __future__ import annotations

from app.agent.Agent import agent
from app.agent.tasks.TaskRecovery import TaskRecovery
from app.config.init_config import init_infra
from app.service import set_cache
from app.utils.logger.logger import logger_agent


def main() -> None:
    """Boot the agent worker."""
    logger_agent.info("Starting SOGo Agent")
    cache, persistency = init_infra()
    set_cache(cache)
    agent.register_lifecycle_hooks(persistency)
    TaskRecovery(agent, persistency, cache).reconcile_orphans()
    logger_agent.info("SOGo Agent ready, entering worker loop")
    agent.start_worker()


if __name__ == "__main__":
    main()
