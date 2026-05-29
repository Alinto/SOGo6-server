"""End-to-end integration test for the Agent.

Spawns a real Celery worker as a subprocess and observes lifecycle through Redis.

Requires the devcontainer's Redis to be reachable. Skipped otherwise.
"""
from __future__ import annotations

import subprocess
import sys
import time
from typing import Any

import pytest

from app.agent.Agent import agent
from app.agent.AgentConst import TASK_RECOVERY_LOCK_KEY
from app.agent.tasks.TaskPersistency import TaskPersistency
from app.agent.tasks.TaskCanceller import TaskCanceller
from app.agent.tasks.TaskStatus import TaskStatus
from app.config.settings.ProcessSetting import process_config
from app.manager.agent.ClientAgent import ClientAgent
from app.manager.cache.ClientRedis import ClientRedis
from tests.test_agent._helpers.TaskTest import TaskTestRequest


_WORKER_BOOT_SECONDS: float = 6.0
_POLL_INTERVAL_SECONDS: float = 0.2
_RESULT_TIMEOUT_SECONDS: float = 20.0

pytestmark = pytest.mark.integration


def _redis_or_skip() -> ClientRedis:
    try:
        client = ClientRedis(
            url_str=process_config.SOGO_P_REDIS_URL,
            resp3=process_config.SOGO_P_REDIS_RESP_3,
        )
        client.redis.ping()
        return client
    except Exception as exc:  # pylint: disable=broad-except
        pytest.skip(f"Redis not reachable: {exc}")


def _start_worker() -> subprocess.Popen:
    proc = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-m", "tests.test_agent._helpers.run_test_worker"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    time.sleep(_WORKER_BOOT_SECONDS)
    if proc.poll() is not None:
        output = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
        raise RuntimeError(f"Worker died at startup:\n{output}")
    return proc


def _stop_worker(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _wait_for_terminal(client: ClientAgent, task_id: str) -> Any:
    deadline = time.monotonic() + _RESULT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        state = client.get(task_id)
        if state is not None and TaskStatus.is_terminal(state.status):
            return state
        time.sleep(_POLL_INTERVAL_SECONDS)
    return client.get(task_id)


@pytest.fixture(name="client")
def _client_fixture():
    cache = _redis_or_skip()
    persistency = TaskPersistency(
        cache, ttl_seconds=process_config.SOGO_P_AGENT_TASK_STATE_TTL_SECONDS,
    )
    canceller = TaskCanceller(agent, persistency)
    yield ClientAgent(agent, persistency, canceller)


@pytest.fixture(name="worker")
def _worker_fixture():
    proc = _start_worker()
    yield proc
    _stop_worker(proc)


def test_happy_path_runs_to_success(client: ClientAgent, worker: subprocess.Popen) -> None:
    assert worker.poll() is None
    task_id = client.start(TaskTestRequest(extras={"k": "v"}))
    state = _wait_for_terminal(client, task_id)
    assert state is not None, "task state never appeared in Redis"
    assert state.status == TaskStatus.SUCCESS, f"unexpected status: {state.status}"
    assert state.result == {"echo": {"k": "v"}, "user_uid": None, "task_id": task_id}
    assert state.attempts == 1
    assert state.date_start is not None and state.date_end is not None


def test_raise_marks_task_as_failure(client: ClientAgent, worker: subprocess.Popen) -> None:
    assert worker.poll() is None
    task_id = client.start(TaskTestRequest(raise_error=True))
    state = _wait_for_terminal(client, task_id)
    assert state is not None
    assert state.status == TaskStatus.FAILURE
    assert state.error and "forced failure" in state.error


def test_task_crash_marks_failure_and_keeps_worker_alive(
    client: ClientAgent, worker: subprocess.Popen,
) -> None:
    """A segfaulting task kills the prefork child, but the master detects it,
    fires ``task_failure`` with a "Worker exited prematurely" exception, then
    respawns a child and keeps serving. The TaskState lands in FAILURE.
    """
    assert worker.poll() is None
    task_id = client.start(TaskTestRequest(crash=True))
    state = _wait_for_terminal(client, task_id)
    assert state is not None
    assert state.status == TaskStatus.FAILURE
    assert state.error and "exited prematurely" in state.error.lower()
    assert worker.poll() is None, "master should survive a child crash"
    # Confirm the master is still serving by running a second task to completion.
    next_id = client.start(TaskTestRequest(extras={"k": "after-crash"}))
    next_state = _wait_for_terminal(client, next_id)
    assert next_state is not None and next_state.status == TaskStatus.SUCCESS


def test_worker_killed_mid_task_recovered_at_next_boot(client: ClientAgent) -> None:
    """Brutal reboot scenario (OOM, deploy, kill -9): worker A is killed while a
    task is STARTED; worker B sweeps the orphan via TaskRecovery at boot.

    TaskTest.resume is False so the orphan is marked FAILURE rather than requeued.
    """
    worker_a = _start_worker()
    try:
        task_id = client.start(TaskTestRequest(seconds=30))
        # Wait until the task is actually running.
        deadline = time.monotonic() + 10.0
        state = None
        while time.monotonic() < deadline:
            state = client.get(task_id)
            if state is not None and state.status == TaskStatus.STARTED:
                break
            time.sleep(_POLL_INTERVAL_SECONDS)
        assert state is not None and state.status == TaskStatus.STARTED, (
            f"task never reached STARTED: {state}"
        )
        worker_a.kill()
        worker_a.wait(timeout=5)
    finally:
        _stop_worker(worker_a)

    # Worker A grabbed the recovery lock at boot (60s TTL). In real prod the next
    # boot would just wait it out; in this test we clear it to keep the run short.
    cache = _redis_or_skip()
    cache.delete(TASK_RECOVERY_LOCK_KEY)

    worker_b = _start_worker()
    try:
        state = _wait_for_terminal(client, task_id)
    finally:
        _stop_worker(worker_b)

    assert state is not None
    assert state.status == TaskStatus.FAILURE
    assert state.error and "not eligible for resume" in state.error
