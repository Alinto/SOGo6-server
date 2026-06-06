"""``poetry run agent`` entrypoint."""
from __future__ import annotations

from app.agent.Agent import agent
from app.agent.jobs.JobRecovery import JobRecovery
from app.config.init_config import init_infra
from app.service import set_cache
from app.utils.logger.logger import logger_agent


def main() -> None:
    """Boot the agent worker.

    The worker does not build a ``ClientAgent``: running jobs reach the large store
    through ``agent.get_large_store()`` and never need the Flask-side facade.
    """
    logger_agent.info("Starting SOGo Agent")
    cache, persistency = init_infra()
    set_cache(cache)
    agent.register_lifecycle_hooks(persistency, cache)
    JobRecovery(agent, persistency, cache).reconcile_orphans()
    logger_agent.info("SOGo Agent ready, entering worker loop")
    agent.start_worker()


if __name__ == "__main__":
    main()
