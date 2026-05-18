# Maximum number of days allowed for events fetch request.
MAX_EVENT_FETCH_DAYS: int = 45

# Maximum number of days allowed for tasks fetch request.
MAX_TASK_FETCH_DAYS: int = 365

# Maximum number of days allowed for a free/busy query.
MAX_FREEBUSY_DAYS: int = 30

# Maximum duration in hours for a single event.
MAX_EVENT_DURATION_HOURS: int = 24

# Maximum length for event text fields (title, location, description).
MAX_EVENT_TITLE_LENGTH: int = 500
MAX_EVENT_LOCATION_LENGTH: int = 500
MAX_EVENT_DESCRIPTION_LENGTH: int = 10000

# Maximum size in bytes for a downloaded ICS feed.
MAX_ICS_BYTES: int = 10 * 1024 * 1024

# Timeout in seconds for HTTP requests to external ICS/CalDAV servers.
FETCH_TIMEOUT_SECONDS: int = 10

# Maximum number of events accepted from an ICS feed during sync.
MAX_ICS_EVENTS: int = 5000

# Maximum number of HTTP redirects followed when fetching an ICS feed.
MAX_ICS_REDIRECTS: int = 3

# TTL in seconds for the Redis sync lock (safety net for stuck syncs).
SYNC_LOCK_TTL_SECONDS: int = 300

# Maximum number of years over which an unbounded recurrence is expanded.
# Hard bound used by RruleEngine.get_max_date when neither UNTIL nor COUNT caps the series.
MAX_RRULE_EXPANSION_YEARS: int = 10
