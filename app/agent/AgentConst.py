"""Hard-coded constants of the Agent runtime — only the values that are *not* meant to be
tunable via environment. Configurable knobs (TTLs, timeouts, concurrency) live in
``ProcessSetting`` under the ``SOGO_P_AGENT_*`` namespace.
"""

# Redis key prefixes — kept in one place so the layout stays consistent across
# TaskPersistency, the admin API and any maintenance script.
TASK_STATE_KEY_PREFIX: str = "taskstate:"
TASK_STATE_INDEX_USER: str = "taskstate:index:user:"           # + user_uid
TASK_STATE_INDEX_PENDING: str = "taskstate:index:pending"
TASK_STATE_INDEX_SCHEDULE: str = "taskstate:index:schedule:"   # + schedule_name
