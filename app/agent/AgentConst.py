"""Process-wide constants for the Agent.

Tunable knobs live in ``ProcessSetting`` as ``SOGO_P_AGENT_*`` (env-overridable
at deploy time). The values defined here are infra invariants — cache key
prefixes, lock identifiers — that should never change without a coordinated
migration of existing data.
"""
from app.agent.jobs.job_result_large_store.JobResultLargeStorage import JobResultLargeStorage


JOB_STATE_KEY_PREFIX: str = "jobstate:"
JOB_STATE_INDEX_USER: str = "jobstate:index:user:"           # + user_uid
JOB_STATE_INDEX_PENDING: str = "jobstate:index:pending"
JOB_STATE_INDEX_SCHEDULE: str = "jobstate:index:schedule:"   # + schedule_name

JOB_RECOVERY_LOCK_KEY: str = "agent:job_recovery:lock"
JOB_RECOVERY_LOCK_TTL_SECONDS: int = 60

JOB_RESULT_LARGE_STORAGE: JobResultLargeStorage = JobResultLargeStorage.FILE
JOB_RESULT_LARGE_KEY_PREFIX: str = "jobresult:"

# Prefix of the lock that serialises enqueues of the same job for the same scope.
# The key itself is built by ``JobState.concurrency_lock_key``. TTL is set per-job
# at acquisition time so a worker crash doesn't leave the slot blocked forever.
JOB_CONCURRENCY_LOCK_PREFIX: str = "agent:concurrency:"
