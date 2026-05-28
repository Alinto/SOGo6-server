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
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun, task_revoked

from app.agent.tasks.TaskStatus import TaskStatus
from app.config.settings.ProcessSetting import ProcessSetting, process_config

if TYPE_CHECKING:
    from app.agent.tasks.Task import Task
    from app.agent.tasks.TaskPersistency import TaskPersistency


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
        user_uid: str | None = None, eta: Any | None = None,
    ) -> str:
        """Schedule a task for execution. Returns the task id.

        ``user_uid`` is optional: system tasks (periodic purge, cluster maintenance, ...)
        are not tied to a user and are enqueued without one.
        """
        result = self._celery.send_task(
            name,
            kwargs={"payload": payload, "user_uid": user_uid},
            eta=eta,
        )
        return str(result.id)

    def cancel(self, task_id: str, *, signal: str = "SIGTERM") -> None:
        """Send a cancel signal to a running task (first step of the 2-phase cancellation).

        The actual hard-kill (SIGKILL) after a soft delay is implemented by ``TaskCanceller``,
        which calls this method twice — once with SIGTERM, then with SIGKILL if needed.
        """
        self._celery.control.revoke(task_id, terminate=True, signal=signal)

    def register(self, task: Task) -> None:
        """Register a :class:`Task` subclass so the worker can execute it.

        Builds the framework-specific wrapper around ``task._run`` and binds it to the
        task name. Soft and hard time limits come from the Task itself (subclass attributes);
        the hard limit is ``soft + 10s``, leaving room for cooperative cleanup.
        """
        soft_limit: int = task.soft_timeout_seconds

        @self._celery.task(  # pylint: disable=unused-variable
            name=task.name, bind=True,
            soft_time_limit=soft_limit, time_limit=soft_limit + 10,
            max_retries=task.max_retry,
        )
        def _wrapper(celery_self: Any, payload: dict[str, Any], user_uid: str | None) -> dict[str, Any]:
            return task._run(celery_self.request.id, payload, user_uid)  # pylint: disable=protected-access

    def register_lifecycle_hooks(self, persistency: TaskPersistency) -> None:
        """Connect framework lifecycle events to TaskPersistency.

        Called once at worker bootstrap. Every running task triggers ``prerun`` → ``postrun``,
        or ``prerun`` → ``failure`` → ``postrun`` on exception, or ``revoked`` on cancel.
        The handlers keep the in-Redis TaskState in sync so the admin API never lies.

        ``weak=False`` keeps the closures alive past the function scope (without it, the
        garbage collector would unsubscribe them after this method returns).
        """

        @task_prerun.connect(weak=False)
        def _on_prerun(task_id: str | None = None, **_: Any) -> None:
            state = persistency.get(task_id) if task_id else None
            if state is None:
                return
            state.status = TaskStatus.STARTED
            state.date_start = datetime.now(timezone.utc)
            state.attempts += 1
            persistency.save(state)

        @task_postrun.connect(weak=False)
        def _on_postrun(
            task_id: str | None = None, state: str | None = None, retval: Any = None, **_: Any,
        ) -> None:
            current = persistency.get(task_id) if task_id else None
            if current is None:
                return
            current.date_end = datetime.now(timezone.utc)
            if current.date_start:
                current.duration_seconds = (current.date_end - current.date_start).total_seconds()
            if state == "SUCCESS":
                current.status = TaskStatus.SUCCESS
                if isinstance(retval, dict):
                    current.result = retval
            elif state == "FAILURE":
                current.status = TaskStatus.FAILURE
            persistency.save(current)

        @task_failure.connect(weak=False)
        def _on_failure(task_id: str | None = None, exception: BaseException | None = None, **_: Any) -> None:
            current = persistency.get(task_id) if task_id else None
            if current is None:
                return
            current.status = TaskStatus.FAILURE
            current.error = str(exception) if exception else None
            persistency.save(current)

        @task_revoked.connect(weak=False)
        def _on_revoked(request: Any = None, **_: Any) -> None:
            task_id = getattr(request, "id", None) if request else None
            current = persistency.get(task_id) if task_id else None
            if current is None:
                return
            current.status = TaskStatus.CANCELED
            current.date_end = datetime.now(timezone.utc)
            if current.date_start:
                current.duration_seconds = (current.date_end - current.date_start).total_seconds()
            persistency.save(current)

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
