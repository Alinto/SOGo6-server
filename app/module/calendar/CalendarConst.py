from datetime import timedelta

# Name given to the personal calendar provisioned for a user at first login.
DEFAULT_CALENDAR_NAME: str = "Personal calendar"

# Maximum number of days allowed for events fetch request.
MAX_EVENT_FETCH_DAYS: int = 45

# Maximum number of days allowed for tasks fetch request.
MAX_TASK_FETCH_DAYS: int = 365

# Maximum number of days allowed for a free/busy query.
MAX_FREEBUSY_DAYS: int = 30

# Default reminder offset in minutes, used when an alarm is created without an explicit
# offset and the parent calendar declares no default_alarm_duration_min of its own.
DEFAULT_REMINDER_MINUTES: int = 15

# Maximum duration in hours for a single event.
MAX_EVENT_DURATION_HOURS: int = 24
MAX_EVENT_ALL_DAY_DURATION_HOURS: int = 14 * 24

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

# When True, importing a .ics file replaces (or injects) the ORGANIZER of every VEVENT/VTODO
# with the importing user's email so the importer becomes the sole owner of the imported
# events. This rewrite leaves the ATTENDEE lines alone — whether they survive the import is
# governed by IMPORT_REMOVES_ATTENDEES below. When False, events are imported as-is — the
# importer ends up owning copies of events organised by someone else, which is generally only
# useful for migrations where the original organiser identity must be preserved.
IMPORT_REWRITES_OWNERSHIP: bool = True

# When True, importing a .ics file strips the ATTENDEE lines of every VEVENT/VTODO so the
# events land as plain personal entries: no guest list is displayed and no iMIP can ever
# target the historical guests on a later edit. When False, attendees are preserved and the
# historical guest list is kept — iMIP would then only fire if the user later edits the
# event explicitly.
IMPORT_REMOVES_ATTENDEES: bool = True

# Maximum size in bytes accepted for an uploaded ICS import payload.
MAX_IMPORT_ICS_BYTES: int = 10 * 1024 * 1024

# Length of the public subscription token. The token is a secret capability, not a mere
# identifier: 64 alphanumeric characters give ~381 bits of entropy, well beyond brute force.
# Uniqueness is guaranteed by the UNIQUE constraint on the share_token column.
SHARE_TOKEN_LENGTH: int = 64

# Suggested resync period advertised in a public subscription feed (REFRESH-INTERVAL /
# X-PUBLISHED-TTL). Twice a day is a sensible default for a personal calendar.
PUBLIC_SUBSCRIPTION_REFRESH: timedelta = timedelta(hours=12)
