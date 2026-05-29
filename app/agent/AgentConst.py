TASK_STATE_KEY_PREFIX: str = "taskstate:"
TASK_STATE_INDEX_USER: str = "taskstate:index:user:"           # + user_uid
TASK_STATE_INDEX_PENDING: str = "taskstate:index:pending"
TASK_STATE_INDEX_SCHEDULE: str = "taskstate:index:schedule:"   # + schedule_name

TASK_RECOVERY_LOCK_KEY: str = "agent:task_recovery:lock"
TASK_RECOVERY_LOCK_TTL_SECONDS: int = 60
