"""Process-wide constants for the Agent.

Tunable knobs live in ``ProcessSetting`` as ``SOGO_P_AGENT_*`` (env-overridable
at deploy time). The values defined here are infra invariants — Redis key
prefixes, lock identifiers — that should never change without a coordinated
migration of existing data.
"""
from app.agent.tasks.task_result_large_store.TaskResultLargeStorage import TaskResultLargeStorage


TASK_STATE_KEY_PREFIX: str = "taskstate:"
TASK_STATE_INDEX_USER: str = "taskstate:index:user:"           # + user_uid
TASK_STATE_INDEX_PENDING: str = "taskstate:index:pending"
TASK_STATE_INDEX_SCHEDULE: str = "taskstate:index:schedule:"   # + schedule_name

TASK_RECOVERY_LOCK_KEY: str = "agent:task_recovery:lock"
TASK_RECOVERY_LOCK_TTL_SECONDS: int = 60

TASK_RESULT_LARGE_STORAGE: TaskResultLargeStorage = TaskResultLargeStorage.IN_MEMORY
TASK_RESULT_LARGE_KEY_PREFIX: str = "taskresult:"
