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
# events. This rewrite leaves the ATTENDEE lines alone - whether they survive the import is
# governed by IMPORT_REMOVES_ATTENDEES below. When False, events are imported as-is - the
# importer ends up owning copies of events organised by someone else, which is generally only
# useful for migrations where the original organiser identity must be preserved.
IMPORT_REWRITES_OWNERSHIP: bool = True

# When True, importing a .ics file strips the ATTENDEE lines of every VEVENT/VTODO so the
# events land as plain personal entries: no guest list is displayed and no iMIP can ever
# target the historical guests on a later edit. When False, attendees are preserved and the
# historical guest list is kept - iMIP would then only fire if the user later edits the
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

# Redis key holding the last time the periodic email-reminder sweep ran (its dedup watermark).
REMINDER_EMAIL_LAST_RUN_KEY: str = "calendar:reminder:email:last_run"
# Window looked back on the very first run, when no watermark exists yet (matches the cron tick).
REMINDER_EMAIL_DEFAULT_WINDOW_MINUTES: int = 1
# TTL of the watermark key - far longer than the cron interval so it never lapses between ticks.
REMINDER_EMAIL_LAST_RUN_TTL_SECONDS: int = 24 * 3600
# Margin (>= one cron tick) that keeps a reminder eligible after its event ends, so a reminder due in
# the firing window is not dropped just because a short event already finished by the time we sweep.
REMINDER_EMAIL_LOOKAHEAD_MINUTES: int = 5

# Subject-line words prepended to outgoing iMIP emails (RFC 6047), one per iTIP method. The
# invitation itself travels in the text/calendar part; these words are only the human-facing
# hint in the Subject header.
#
# TODO: these strings MUST be translated. They are the only user-facing text left in an iMIP
# email (the body is now language-neutral text/calendar) and are currently hard-coded English.
# There is no i18n backend yet: the SOGO_U_LANGUAGE user preference exists but is never read
# server-side. When a translation mechanism lands, resolve these per recipient locale instead
# of using the constants below.
IMIP_SUBJECT_PREFIX_REQUEST: str = "Invitation"
IMIP_SUBJECT_PREFIX_REPLY: str = "Re"
IMIP_SUBJECT_PREFIX_CANCEL: str = "Cancelled"

# User-facing words of the email reminder message (subject prefix + body labels).
#
# TODO: these strings MUST be translated, exactly like the iMIP subject prefixes above. They are the
# only user-facing text in a reminder email and are currently hard-coded English. There is no i18n
# backend yet (SOGO_U_LANGUAGE is never read server-side); when a translation mechanism lands, resolve
# them per recipient locale instead of using the constants below. Handle them together with the iMIP
# prefixes.
REMINDER_EMAIL_SUBJECT_PREFIX: str = "Reminder"
REMINDER_EMAIL_WHEN_LABEL: str = "When"
REMINDER_EMAIL_WHERE_LABEL: str = "Where"
REMINDER_EMAIL_DEFAULT_TITLE: str = "Event"  # fallback when the event has no title

# When a non-organizer attendee modifies an event they received, the server compares the submitted
# event to the stored copy and rejects (ERROR_CALENDAR_NOT_ORGANIZER) any change to organizer-owned
# content. This is only correct when the submission carries just the changed fields: an update that
# re-states the whole event (echoing an occurrence's date, or dropping EXDATE) triggers a FALSE
# rejection. The intended usage is a minimal update (only the changed fields), so this flag stays True.
# Set to False to instead silently keep only the attendee's personal fields (reminders, conference
# data) and ignore any organizer-content drift - lenient toward whole-event submissions, but a genuine
# content change by an attendee is then dropped with no feedback. This flag is the server-side safety
# net for the tolerant behavior.
REJECT_ATTENDEE_CONTENT_CHANGE: bool = True
