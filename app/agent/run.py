"""Agent entrypoints: ``poetry run agent`` (worker) and ``poetry run agent-beat`` (scheduler)."""
from __future__ import annotations

import threading

from app.agent.AgentConst import BEAT_LOCK_KEY, BEAT_LOCK_TTL_SECONDS
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


def beat() -> None:
    """Boot the Celery Beat scheduler, guarded so only one instance is ever active.

    Acquires a Redis lock with a TTL and refreshes it from a background thread while
    beat runs; if another beat already holds it, this process exits without scheduling.
    The lock auto-expires if the holder crashes, so another instance can take over.
    """
    logger_agent.info("Starting SOGo Agent Beat")
    cache, _ = init_infra()
    set_cache(cache)
    ttl: int = BEAT_LOCK_TTL_SECONDS
    if not cache.set(BEAT_LOCK_KEY, "1", ttl=ttl, nx=True):
        logger_agent.error("Another agent-beat instance is already running; exiting.")
        return
    stop: threading.Event = threading.Event()

    def _refresh_lock() -> None:
        # Keep the lock alive while beat runs; if beat dies, the TTL lets it lapse.
        while not stop.wait(ttl / 2):
            cache.set(BEAT_LOCK_KEY, "1", ttl=ttl)

    heartbeat: threading.Thread = threading.Thread(target=_refresh_lock, daemon=True)
    heartbeat.start()
    try:
        agent.start_beat()
    finally:
        stop.set()
        cache.delete(BEAT_LOCK_KEY)


if __name__ == "__main__":
    main()
