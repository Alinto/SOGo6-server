from __future__ import annotations

# Maximum number of days allowed for events fetch request.
MAX_EVENT_FETCH_DAYS: int = 31

# Maximum number of days allowed for tasks fetch request.
MAX_TASK_FETCH_DAYS: int = 365

# Maximum size in bytes for a downloaded ICS feed.
MAX_ICS_BYTES: int = 10 * 1024 * 1024

# Timeout in seconds for HTTP requests to external ICS/CalDAV servers.
FETCH_TIMEOUT_SECONDS: int = 10
