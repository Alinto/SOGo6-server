"""Entrypoint for the SOGo Agent process: ``poetry run agent`` boots an Agent worker.

This module knows nothing about the underlying task framework — all configuration and
command-line construction live in ``AgentApp.start_worker``.
"""
from __future__ import annotations

from app.agent.AgentApp import agent
from app.utils.logger.logger import logger


def main() -> None:
    """Start the Agent worker (with embedded Beat). Settings come from ``ProcessSetting``."""
    logger.info("Starting SOGo Agent")
    agent.start_worker()


if __name__ == "__main__":
    main()
