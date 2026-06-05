"""``poetry run agent`` entrypoint."""
from __future__ import annotations

from app.agent.Agent import agent
from app.agent.jobs.JobCanceller import JobCanceller
from app.agent.jobs.JobRecovery import JobRecovery
from app.config.init_config import init_infra
from app.manager.agent.ClientAgent import ClientAgent
from app.service import set_agent, set_cache
from app.utils.logger.logger import logger_agent


def main() -> None:
    """Boot the agent worker."""
    logger_agent.info("Starting SOGo Agent")
    cache, persistency = init_infra()
    set_cache(cache)
    # Expose a ClientAgent in the worker too: a running job may enqueue a sub-job
    # (e.g. fan-out, follow-up). Without this, ``sogo_agent()`` would raise inside
    # ``Job.process``.
    set_agent(ClientAgent(agent, persistency, JobCanceller(agent, persistency), cache))
    agent.register_lifecycle_hooks(persistency, cache)
    JobRecovery(agent, persistency, cache).reconcile_orphans()
    logger_agent.info("SOGo Agent ready, entering worker loop")
    agent.start_worker()


if __name__ == "__main__":
    main()
