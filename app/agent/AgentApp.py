"""Celery is encapsulated behind a single class, ``AgentApp``.

The name is intentionally agnostic of the underlying framework: no other file in the
project imports ``celery`` directly — they all go through the ``agent`` instance below.
If we ever swap Celery for another task framework, only this file changes.

Process-wide settings (concurrency, prefetch, visibility, TTL, Beat schedule path) are
exposed as ``SOGO_P_*`` process settings — never hardcoded here. Per-task settings
(timeouts, retry policy) live on the Task subclasses themselves.
"""
from __future__ import annotations

import os
from typing import Any

from celery import Celery

from app.config.settings.ProcessSetting import ProcessSetting, process_config


class AgentApp:
    """Wraps the underlying task framework (currently Celery) and exposes a domain API.

    Application code calls :meth:`create_task` / :meth:`cancel` / :meth:`register`.
    The underlying Celery instance is private (``_celery``) and never leaks into the
    rest of the codebase.
    """

    def __init__(self, process_setting: ProcessSetting) -> None:
        self._process_setting: ProcessSetting = process_setting
        self._celery: Celery = Celery(
            "sogo_agent",
            broker=process_setting.SOGO_P_REDIS_URL,
            backend=process_setting.SOGO_P_REDIS_URL,
        )
        self._celery.conf.update(
            # Reserved messages are only acknowledged after the task completes — a crashed
            # worker re-delivers the task instead of silently losing it.
            task_acks_late=True,
            # A task killed mid-flight (worker lost, OOM) must not be silently re-queued
            # forever: we let the higher-level retry policy decide.
            task_reject_on_worker_lost=False,
            worker_prefetch_multiplier=process_setting.SOGO_P_AGENT_WORKER_PREFETCH_MULTIPLIER,
            # Required for STARTED state to appear in lifecycle hooks (task_prerun) —
            # without it the task jumps from PENDING straight to SUCCESS/FAILURE.
            task_track_started=True,
            # Redis visibility timeout: must exceed the longest task we run, otherwise
            # Redis re-queues an in-flight task and we get phantom double executions.
            broker_transport_options={
                "visibility_timeout": process_setting.SOGO_P_AGENT_BROKER_VISIBILITY_TIMEOUT_SECONDS,
            },
            # Defensive socket timeouts: avoid silent connection stalls under network blips.
            broker_connection_retry_on_startup=True,
            redis_socket_connect_timeout=5,
            redis_socket_keepalive=True,
            # JSON serialisation — human-readable in Redis and cross-language compatible.
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            timezone="UTC",
            enable_utc=True,
        )

    def create_task(
        self, name: str, payload: dict[str, Any], *,
        user_uid: str, domain: str, eta: Any | None = None,
    ) -> str:
        """Schedule a task for execution. Returns the task id."""
        result = self._celery.send_task(
            name,
            kwargs={"payload": payload, "user_uid": user_uid, "domain": domain},
            eta=eta,
        )
        return str(result.id)

    def cancel(self, task_id: str, *, signal: str = "SIGTERM") -> None:
        """Send a cancel signal to a running task (first step of the 2-phase cancellation).

        The actual hard-kill (SIGKILL) after a soft delay is implemented by ``TaskCanceller``,
        which calls this method twice — once with SIGTERM, then with SIGKILL if needed.
        """
        self._celery.control.revoke(task_id, terminate=True, signal=signal)

    def start_worker(self) -> None:
        """Run a worker process with the embedded Beat scheduler.

        Builds the framework-specific command-line entirely from process settings —
        callers never have to know about Celery flags. ``--without-mingle/gossip/
        heartbeat`` disable inter-worker Redis pub/sub features that are useless in a
        mono-worker setup and require extra Redis ACL permissions.
        """
        concurrency: int = self._process_setting.SOGO_P_AGENT_WORKER_CONCURRENCY
        schedule_path: str = self._process_setting.SOGO_P_AGENT_BEAT_SCHEDULE_PATH
        # Beat opens the schedule file via ``Path.touch`` and does not create the parent
        # directory itself — we make sure it exists so the worker starts cleanly.
        os.makedirs(os.path.dirname(schedule_path), exist_ok=True)
        argv: list[str] = [
            "worker", "--beat", "-l", "INFO",
            "--concurrency", str(concurrency),
            "--schedule", schedule_path,
            "--without-mingle", "--without-gossip", "--without-heartbeat",
        ]
        self._celery.worker_main(argv)

    @property
    def for_celery_cli(self) -> Celery:
        """Expose the underlying Celery instance to the ``celery -A ...`` CLI only.

        DO NOT use this from application code — go through the domain methods above.
        It exists solely because the ``celery worker`` / ``celery beat`` native commands
        need to locate an instance via module-level lookup.
        """
        return self._celery


# Process-wide singleton: application code imports `agent` and never touches Celery.
agent: AgentApp = AgentApp(process_config)

# Module-level alias for the native `celery -A app.agent.AgentApp worker/beat` CLI to find
# the Celery instance. Reserved for the CLI; application code MUST go through `agent`.
celery_app: Celery = agent.for_celery_cli
