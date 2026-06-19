from app.utils.db.Table import Column, Index, Table
from app.config.settings.ProcessSetting import process_config



COL_ID   = Column(name="id", data_type="serial") #No need to set is_unique=True for this one
COL_HASH = Column(name="hash", data_type="str", is_unique=True)

##############################
# Table sogo_settings_system #
##############################
"""
Only one query to fecth all
SELECT TOP 1 * from sogo_settings WHERE id = 1;
"""
# settings_unique is just a watchguard to make sure there is only one row in this table
# settings_system: sogo's system settings
# settings_domain_default: sogo's domain default settings
COL_SETTINGS_UNIQUE         = Column(name="settings_unique", data_type="int8")
COL_SETTINGS_SYSTEM         = Column(name="settings_system", data_type="dict")
COL_SETTINGS_DOMAIN_DEFAULT = Column(name="settings_domain_default", data_type="dict")
ALL_SETTINGS_COL            = [COL_SETTINGS_UNIQUE,
                               COL_SETTINGS_SYSTEM,
                               COL_SETTINGS_DOMAIN_DEFAULT]
TABLE_SETTINGS = Table(name=process_config.SOGO_P_TABLE_SETTINGS, columns=ALL_SETTINGS_COL, primary_keys=(COL_SETTINGS_UNIQUE.name,))

###############################
# Table sogo_settings_domains #
###############################
"""
Query to fecth the settings from a domain for every authenticated API request
SELECT domain_settings from sogo_settings_domains WHERE domain_name = <domain>;

Query to fetch the settings and their origins for the config interface
SELECT domain_settings,domain_origin from sogo_settings_domains WHERE domain_name = <domain>;
"""
# domain_name: Name of the domain
# domain_description: Description of the domain if needed
# domain_info: Info for this domain
# domain_settings: Settings of this domain
# domain_origin: Origin of the tsettings (default sogo, default admin, rule's name or direct)
# domain_user_defaults: all user settings with value force by the admin
COL_DOMAIN_NAME          = Column(name="domain_name", data_type="str", extra_args={"max_len": 255}, is_unique=True) #max length is 255 -> https://www.rfc-editor.org/rfc/rfc1035#section-2.3.4
COL_DOMAIN_DESCRIPTION   = Column(name="domain_description", data_type="str", is_nullable=True)
COL_DOMAIN_INFO          = Column(name="domain_info", data_type="str", is_nullable=True)
COL_DOMAIN_SETTINGS      = Column(name="domain_settings", data_type="dict")
COL_DOMAIN_ORIGIN        = Column(name="domain_origins", data_type="dict")
COL_DOMAIN_USER_DEFAULTS = Column(name="domain_user_defaults", data_type="dict")
ALL_DOMAIN_COL           = [COL_ID,
                            COL_HASH,
                            COL_DOMAIN_NAME,
                            COL_DOMAIN_DESCRIPTION,
                            COL_DOMAIN_INFO,
                            COL_DOMAIN_SETTINGS,
                            COL_DOMAIN_ORIGIN]
TABLE_DOMAIN = Table(name=process_config.SOGO_P_TABLE_DOMAINS, columns=ALL_DOMAIN_COL, primary_keys=(COL_ID.name, COL_HASH.name, COL_DOMAIN_NAME.name))

#############################
# Table sogo_settings_rules #
#############################
"""
Query to fecth the settings from a domain for every authenticated API request
SELECT domain_settings from sogo_settings_domains WHERE domain_name = <domain>;

Query to fect hthe settings and their origins for the config interface
SELECT domain_settings,domain_origin from sogo_settings_domains WHERE domain_name = <domain>;
"""
# rule_name: Name of the rule
# rule_description: Description of the rule
# rule_domains: domains affected by this rule
# rule_setting: Settings affected by this rule
COL_RULE_NAME        = Column(name="rule_name", data_type="str", is_unique=True, extra_args={"max_len": 255})
COL_RULE_DESCRIPTION = Column(name="rule_description", data_type="str")
COL_RULE_DOMAINS     = Column(name="rule_domains", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 255}})
COL_RULE_SETTINGS    = Column(name="rule_setting", data_type="dict")
ALL_RULE_COL      = [COL_ID,
                     COL_HASH,
                     COL_RULE_NAME,
                     COL_RULE_DOMAINS,
                     COL_RULE_SETTINGS]
TABLE_RULES = Table(name=process_config.SOGO_P_TABLE_RULES, columns=ALL_RULE_COL, primary_keys=(COL_ID.name, COL_HASH.name, COL_RULE_NAME.name))

#############################
# Table sogo_user_profiles #
#############################
"""
All queries will have WHERE uid = <uid>
"""
# uid: full email of the user, even if the login is domainless
# defaults: default user preferences
# folders: folders id and name for this user
# main_account: main account settings of this user
# external_accounts: external accounts linked to this user
# filters: sieve filters of this user
# private_salt: unique salt generated for the user.
# acl_given: acl given to users
# acl_received: acl received from users
# delegation_given: delegation given to users
# delegation_received: delegation received from users
COL_USER_UID              = Column(name="uid", data_type="str", extra_args={"max_len": 512}, is_unique=True)
COL_USER_DEFAULTS         = Column(name="preferences", data_type="dict")
COL_USER_FOLDERS          = Column(name="folders", data_type="dict")
COL_USER_MAIN_ACCOUNT     = Column(name="main_account", data_type="dict")
COL_USER_EXTERNAL_ACCOUNTS = Column(name="external_accounts", data_type="dict", is_nullable=True)
COL_USER_FILTERS          = Column(name="filters", data_type="dict", is_nullable=True)
COL_USER_PRIVATE_SALT     = Column(name="private_salt", data_type= "str", extra_args={"max_len": 4096})
COL_USER_ACL_GIVEN        = Column(name="acl_given", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 512}}, is_nullable=True)
COL_USER_ACL_GOT          = Column(name="acl_received", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 512}}, is_nullable=True)
COL_USER_DELEGATION_GIVEN = Column(name="delegation_given", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 512}}, is_nullable=True)
COL_USER_DELEGATION_GOT   = Column(name="delegation_received", data_type="list", extra_args={"data_type": "str", "extra_args": {"max_len": 512}}, is_nullable=True)
ALL_USER_COL              = [COL_ID,
                             COL_HASH,
                             COL_USER_UID,
                             COL_USER_DEFAULTS,
                             COL_USER_FOLDERS,
                             COL_USER_MAIN_ACCOUNT,
                             COL_USER_EXTERNAL_ACCOUNTS,
                             COL_USER_FILTERS,
                             COL_USER_PRIVATE_SALT,
                             COL_USER_ACL_GIVEN,
                             COL_USER_ACL_GOT,
                             COL_USER_DELEGATION_GIVEN,
                             COL_USER_DELEGATION_GOT,
                             ]
TABLE_USER = Table(name=process_config.SOGO_P_TABLE_USERS, columns=ALL_USER_COL, primary_keys=(COL_ID.name, COL_HASH.name, COL_USER_UID.name,))



########################
# Table sogo_calendars #
########################
"""
Stores personal and external calendars for each user.
All queries use WHERE user_uid = <uid>.
External calendars (.ics / CalDAV) are differentiated by source_type;
their sync metadata is stored in sync_config JSON to avoid polluting
the schema with nullable columns only relevant to non-local calendars.
"""
# key: opaque token exposed in the API instead of id to prevent row enumeration (see sogo_hash.py HASH_SIZE_CALENDAR)
# user_uid: owner of this calendar — FK to sogo_user_profiles.uid — present in every WHERE clause
# is_default: marks the user's primary personal calendar; only one per user, enforced by service layer
# source_type: discriminates calendar origin — 'local' (personal, full CRUD), 'ics' (read-only WebDAV subscription), 'caldav' (read-write CalDAV)
# name: display name shown in the UI
# color: hex color code (#RRGGBB) used to visually differentiate calendars
# description: optional free-text description, nullable
# timezone: default IANA timezone applied to events created in this calendar (e.g. Europe/Paris)
# share_token: opaque token for the public .ics subscription URL — queried directly (WHERE share_token = ?) so must be a relational column, not JSON
# ctag: collection tag incremented by the service layer on every event mutation — allows CalDAV clients to detect changes without listing all events (RFC 4791 / getctag extension)
# sync_config: JSON blob grouping all external sync metadata — url, username, password (encrypted with SOGO_AES_ENC_KEY), etag, last_sync, cached_data, sync_interval_minutes — NULL for source_type='local'
# include_in_freebusy: when FALSE, this calendar's events are excluded from the owner's free/busy aggregation; relational so it can gate the aggregation like is_default
# preferences: JSON blob grouping the calendar's new-event UI defaults (default_event_duration_min, default_alarm_duration_min, default_type) — never filtered/sorted, NULL when none set
# created_at / updated_at: UTC timestamps stored as DATETIME
COL_CAL_KEY               = Column(name="key",                data_type="str",      is_unique=True,                    extra_args={"max_len": 64})
COL_CAL_USER_UID          = Column(name="user_uid",           data_type="str",                                         extra_args={"max_len": 512})
COL_CAL_IS_DEFAULT        = Column(name="is_default",         data_type="bool")
COL_CAL_SOURCE_TYPE       = Column(name="source_type",        data_type="str",                                         extra_args={"max_len": 6})
COL_CAL_NAME              = Column(name="name",               data_type="str",                                         extra_args={"max_len": 255})
COL_CAL_COLOR             = Column(name="color",              data_type="str",      is_nullable=True,                extra_args={"max_len": 7})
COL_CAL_DESCRIPTION       = Column(name="description",        data_type="text",     is_nullable=True)
COL_CAL_TIMEZONE          = Column(name="timezone",           data_type="str",                                         extra_args={"max_len": 64})
COL_CAL_SHARE_TOKEN       = Column(name="share_token",        data_type="str",      is_unique=True, is_nullable=True,  extra_args={"max_len": 64})
COL_CAL_CTAG              = Column(name="ctag",               data_type="int")
COL_CAL_SYNC_CONFIG       = Column(name="sync_config",        data_type="dict",     is_nullable=True)
COL_CAL_INCLUDE_IN_FB     = Column(name="include_in_freebusy", data_type="bool")
COL_CAL_PREFERENCES       = Column(name="preferences",        data_type="dict",     is_nullable=True)
COL_CAL_CREATED_AT        = Column(name="created_at",         data_type="datetime")
COL_CAL_UPDATED_AT        = Column(name="updated_at",         data_type="datetime")

ALL_CAL_COL = [COL_ID,
               COL_CAL_KEY,
               COL_CAL_USER_UID,
               COL_CAL_IS_DEFAULT,
               COL_CAL_SOURCE_TYPE,
               COL_CAL_NAME,
               COL_CAL_COLOR,
               COL_CAL_DESCRIPTION,
               COL_CAL_TIMEZONE,
               COL_CAL_SHARE_TOKEN,
               COL_CAL_CTAG,
               COL_CAL_SYNC_CONFIG,
               COL_CAL_INCLUDE_IN_FB,
               COL_CAL_PREFERENCES,
               COL_CAL_CREATED_AT,
               COL_CAL_UPDATED_AT]

IDX_CAL_USER_UID = Index(name="idx_cal_user_uid", columns=(COL_CAL_USER_UID.name,))

TABLE_CALENDAR = Table(name=process_config.SOGO_P_TABLE_CALENDARS, columns=ALL_CAL_COL, primary_keys=(COL_ID.name, COL_CAL_KEY.name),
                       indexes=[IDX_CAL_USER_UID])

#####################
# Table sogo_events #
#####################
"""
Stores all calendar components (VEVENT, VTODO, VJOURNAL) for personal calendars.
Pattern: relational columns only for SQL filtering/sorting; the full RFC 5545
component is serialized in cal_event JSON (title, description, timezone, attendees, etc.).

Key queries:
  SELECT ... FROM sogo_events WHERE calendar_id = ? AND is_deleted = FALSE AND date_start <= ? AND date_end >= ?
  SELECT ... FROM sogo_events WHERE calendar_id = ? AND is_recurring = TRUE AND (date_end_recurrence IS NULL OR date_end_recurrence >= ?)
  SELECT ... FROM sogo_events WHERE calendar_id = ? AND show_as = 'busy' AND is_deleted = FALSE  (FreeBusy)
"""
# key: opaque token exposed in the API instead of id (see sogo_hash.py HASH_SIZE_EVENT)
# calendar_id: FK to sogo_calendars.id — present in every WHERE clause
# uid: RFC 5545 UID — unique per (calendar_id, uid); same uid appears in multiple calendars for iMIP copies (organizer + each attendee has their own row)
# component_type: domain type of the component — 'event', 'task', 'journal'; maps to RFC 5545 VEVENT/VTODO/VJOURNAL in the iCal layer
# date_start: DTSTART in UTC — lower bound for date range queries
# date_end: DTEND in UTC for VEVENT/VJOURNAL, DUE in UTC for VTODO; all-day events store DTEND-1s (DTEND is exclusive in RFC 5545, -1s makes SQL range queries inclusive)
# show_as: RFC 5545 TRANSP — 'busy' (OPAQUE) or 'free' (TRANSPARENT) or 'out-of-office' / 'tentative' (Microsoft extensions); used in FreeBusy queries
# is_recurring: TRUE when the event has an RRULE; discriminator for the dual SQL range
#   strategy — date_end_recurrence alone cannot serve this role because unbounded recurring series have date_end_recurrence = NULL, same as non-recurring events
# date_end_recurrence: UTC datetime of the last occurrence's end; NULL for infinite recurrences; used with is_recurring = TRUE for efficient date range queries
# recurrence_id: UTC datetime of the original occurrence this row replaces (RFC 5545 RECURRENCE-ID); NULL on master events; used for CalDAV per-occurrence addressing and THISANDFUTURE operations
# is_deleted: soft delete flag — never DELETE FROM sogo_events; deleted events return HTTP 404 in CalDAV sync reports (RFC 4791)
# sequence: RFC 5545 SEQUENCE — incremented by the organizer on each modification; attendees use it to detect whether a received iMIP message supersedes their current copy
# search_vector: aggregation of title + description + location maintained by the service layer; a single full-text column, stored as tsvector (GIN index) on PostgreSQL and as TEXT (FULLTEXT index) on MariaDB
# cal_event: full serialized RFC 5545 component as JSON — contains all properties not needed for SQL filtering: title, description, location, url, timezone_start, timezone_end, all_day, status, visibility, color, priority, dtstamp, organizer, attendees, reminders, conference_data, attachments, recurrence_range (THISANDFUTURE), percent_complete (VTODO), completed_at (VTODO)
# created_at / updated_at: UTC timestamps; updated_at serves as RFC 5545 LAST-MODIFIED when serializing to iCalendar
COL_EVT_KEY               = Column(name="key",                  data_type="str",      is_unique=True,               extra_args={"max_len": 64})
COL_EVT_CALENDAR_KEY      = Column(name="calendar_key",         data_type="str",      extra_args={"max_len": 64})
COL_EVT_UID               = Column(name="uid",                  data_type="str",                                    extra_args={"max_len": 512})
COL_EVT_COMPONENT_TYPE    = Column(name="component_type",       data_type="str",                                    extra_args={"max_len": 10})
COL_EVT_DATE_START        = Column(name="date_start",           data_type="datetime")
COL_EVT_DATE_END          = Column(name="date_end",             data_type="datetime", is_nullable=True)
COL_EVT_SHOW_AS           = Column(name="show_as",              data_type="str",                                    extra_args={"max_len": 12})
COL_EVT_IS_RECURRING      = Column(name="is_recurring",         data_type="bool")
COL_EVT_DATE_END_RECUR    = Column(name="date_end_recurrence",  data_type="datetime", is_nullable=True)
COL_EVT_RECURRENCE_ID     = Column(name="recurrence_id",        data_type="datetime", is_nullable=True)
COL_EVT_IS_DELETED        = Column(name="is_deleted",           data_type="bool")
COL_EVT_SEQUENCE          = Column(name="sequence",             data_type="int")
COL_EVT_SEARCH_VECTOR     = Column(name="search_vector",        data_type="tsvector")
COL_EVT_CAL_EVENT         = Column(name="cal_event",            data_type="dict")
COL_EVT_CREATED_AT        = Column(name="created_at",           data_type="datetime")
COL_EVT_UPDATED_AT        = Column(name="updated_at",           data_type="datetime")

ALL_EVT_COL = [COL_ID,
               COL_EVT_KEY,
               COL_EVT_CALENDAR_KEY,
               COL_EVT_UID,
               COL_EVT_COMPONENT_TYPE,
               COL_EVT_DATE_START,
               COL_EVT_DATE_END,
               COL_EVT_SHOW_AS,
               COL_EVT_IS_RECURRING,
               COL_EVT_DATE_END_RECUR,
               COL_EVT_RECURRENCE_ID,
               COL_EVT_IS_DELETED,
               COL_EVT_SEQUENCE,
               COL_EVT_SEARCH_VECTOR,
               COL_EVT_CAL_EVENT,
               COL_EVT_CREATED_AT,
               COL_EVT_UPDATED_AT]

IDX_EVT_CALENDAR_KEY = Index(name="idx_evt_calendar_key", columns=(COL_EVT_CALENDAR_KEY.name,))
IDX_EVT_DATE_RANGE = Index(name="idx_evt_date_range", columns=(COL_EVT_CALENDAR_KEY.name, COL_EVT_DATE_START.name, COL_EVT_DATE_END.name))
IDX_EVT_UID = Index(name="idx_evt_uid", columns=(COL_EVT_UID.name,))
# Dedicated full-text structure, not a btree: GIN on the tsvector column (PostgreSQL) / FULLTEXT
# on the TEXT column (MariaDB, where MATCH ... AGAINST requires it).
IDX_EVT_SEARCH = Index(name="idx_evt_search_vector", columns=(COL_EVT_SEARCH_VECTOR.name,), fulltext=True)

TABLE_EVENT = Table(name=process_config.SOGO_P_TABLE_EVENTS, columns=ALL_EVT_COL, primary_keys=(COL_ID.name, COL_EVT_KEY.name),
                    indexes=[IDX_EVT_CALENDAR_KEY, IDX_EVT_DATE_RANGE, IDX_EVT_UID, IDX_EVT_SEARCH])

##############################
# Table sogo_calendar_reminders #
##############################
# Materialized reminders for SQL-level filtering.
# Each row corresponds to one reminder on one event. trigger_at is pre-computed
# as event.date_start - minutes_before for efficient range queries.
# calendar_key and user_uid are not stored — obtain via JOIN on sogo_events / sogo_calendars.
# is_deleted: soft delete flag, purged by the clean maintenance task.
COL_REM_EVENT_KEY    = Column(name="event_key",      data_type="str",      extra_args={"max_len": 64})
COL_REM_METHOD       = Column(name="method",         data_type="str",      extra_args={"max_len": 10})
COL_REM_MINUTES      = Column(name="minutes_before", data_type="int")
COL_REM_TRIGGER_AT   = Column(name="trigger_at",     data_type="datetime")
COL_REM_IS_DELETED   = Column(name="is_deleted",     data_type="bool")
COL_REM_CREATED_AT   = Column(name="created_at",     data_type="datetime")
COL_REM_UPDATED_AT   = Column(name="updated_at",     data_type="datetime")

ALL_REM_COL = [COL_ID,
               COL_REM_EVENT_KEY,
               COL_REM_METHOD,
               COL_REM_MINUTES,
               COL_REM_TRIGGER_AT,
               COL_REM_IS_DELETED,
               COL_REM_CREATED_AT,
               COL_REM_UPDATED_AT]

IDX_REM_TRIGGER = Index(name="idx_rem_trigger", columns=(COL_REM_TRIGGER_AT.name, COL_REM_IS_DELETED.name))
IDX_REM_EVENT_KEY = Index(name="idx_rem_event_key", columns=(COL_REM_EVENT_KEY.name,))

TABLE_REMINDER = Table(name=process_config.SOGO_P_TABLE_REMINDERS, columns=ALL_REM_COL, primary_keys=(COL_ID.name,),
                       indexes=[IDX_REM_TRIGGER, IDX_REM_EVENT_KEY])

####################################
# Table sogo6_contacts_addressbooks #
####################################
"""
Stores personal and external address books for each user.
All queries use WHERE user_uid = <uid>.
The address book is the unit of sharing: contacts belong to exactly one book.
External CardDAV books are differentiated by source_type; their sync metadata lives in sync_config JSON.
"""
# key: opaque token exposed in the API instead of id to prevent row enumeration
# user_uid: owner of this address book - FK to sogo_user_profiles.uid - present in every WHERE clause
# is_default: marks the user's primary address book; only one per user, enforced by the service layer
# source_type: discriminates the backend - 'local' (DB, full CRUD) or 'carddav' (read-write CardDAV)
# name: display name shown in the UI
# description: optional free-text description, nullable
# ctag: collection tag bumped by the service layer on every contact mutation - CardDAV change detection (RFC 6352)
# sync_config: JSON blob grouping external CardDAV sync metadata - NULL for source_type='local'
# created_at / updated_at: UTC timestamps stored as DATETIME
COL_AB_KEY                = Column(name="key",            data_type="str",      is_unique=True,                    extra_args={"max_len": 64})
COL_AB_USER_UID           = Column(name="user_uid",       data_type="str",                                         extra_args={"max_len": 512})
COL_AB_IS_DEFAULT         = Column(name="is_default",     data_type="bool")
COL_AB_SOURCE_TYPE        = Column(name="source_type",    data_type="str",                                         extra_args={"max_len": 8})
COL_AB_NAME               = Column(name="name",           data_type="str",                                         extra_args={"max_len": 255})
COL_AB_DESCRIPTION        = Column(name="description",    data_type="text",     is_nullable=True)
COL_AB_CTAG               = Column(name="ctag",           data_type="int")
COL_AB_SYNC_CONFIG        = Column(name="sync_config",    data_type="dict",     is_nullable=True)
COL_AB_CREATED_AT         = Column(name="created_at",     data_type="datetime")
COL_AB_UPDATED_AT         = Column(name="updated_at",     data_type="datetime")

ALL_AB_COL = [COL_ID,
              COL_AB_KEY,
              COL_AB_USER_UID,
              COL_AB_IS_DEFAULT,
              COL_AB_SOURCE_TYPE,
              COL_AB_NAME,
              COL_AB_DESCRIPTION,
              COL_AB_CTAG,
              COL_AB_SYNC_CONFIG,
              COL_AB_CREATED_AT,
              COL_AB_UPDATED_AT]

IDX_AB_USER_UID = Index(name="idx_ab_user_uid", columns=(COL_AB_USER_UID.name,))

TABLE_ADDRESSBOOK = Table(name=process_config.SOGO_P_TABLE_ADDRESSBOOKS, columns=ALL_AB_COL,
                          primary_keys=(COL_ID.name, COL_AB_KEY.name), indexes=[IDX_AB_USER_UID])

###############################
# Table sogo6_contacts_contacts #
###############################
"""
Stores all contacts (vCard, RFC 6350) of an address book.
Pattern: relational columns only for SQL filtering/sorting; the full vCard fiche is serialized
in the contact_data JSON blob (names, emails, phones, addresses, etc.).

Key queries:
  SELECT ... FROM sogo6_contacts_contacts WHERE addressbook_key = ? AND is_deleted = FALSE ORDER BY last_name, first_name
  SELECT ... WHERE addressbook_key = ? AND is_deleted = FALSE AND MATCH(search_vector) ...  (autocompletion / search)
"""
# key: opaque token exposed in the API instead of id
# addressbook_key: FK to sogo6_contacts_addressbooks.key - present in every WHERE clause
# uid: vCard UID - expected unique per (addressbook_key, uid), but NOT enforced at the DB level yet
#   (the REST API generates the uid itself; a real unique constraint is needed once CardDAV clients
#   own the uid - RFC 6352)
# kind: vCard KIND - 'individual', 'org', 'group'
# last_name / first_name / organization: relational copies of the name parts, for ORDER BY and filtering
# display_name: vCard FN - the formatted name shown in listings
# is_deleted: soft delete flag - never DELETE FROM (required for CardDAV sync reports, RFC 6352)
# search_vector: aggregation of the textual fields maintained by the service layer; tsvector (GIN) on
#   PostgreSQL, TEXT (FULLTEXT) on MariaDB
# contact_data: full vCard fiche as JSON - everything not promoted to a relational column
# created_at / updated_at: UTC timestamps
COL_CT_KEY                = Column(name="key",            data_type="str",      is_unique=True,                    extra_args={"max_len": 64})
COL_CT_ADDRESSBOOK_KEY    = Column(name="addressbook_key", data_type="str",      is_nullable=True,                  extra_args={"max_len": 64})
COL_CT_UID                = Column(name="uid",            data_type="str",                                         extra_args={"max_len": 512})
COL_CT_KIND               = Column(name="kind",           data_type="str",                                         extra_args={"max_len": 12})
COL_CT_LAST_NAME          = Column(name="last_name",      data_type="str",      is_nullable=True,                  extra_args={"max_len": 255})
COL_CT_FIRST_NAME         = Column(name="first_name",     data_type="str",      is_nullable=True,                  extra_args={"max_len": 255})
COL_CT_ORGANIZATION       = Column(name="organization",   data_type="str",      is_nullable=True,                  extra_args={"max_len": 255})
COL_CT_DISPLAY_NAME       = Column(name="display_name",   data_type="str",                                         extra_args={"max_len": 255})
COL_CT_IS_DELETED         = Column(name="is_deleted",     data_type="bool")
COL_CT_SEARCH_VECTOR      = Column(name="search_vector",  data_type="tsvector")
COL_CT_CONTACT_DATA       = Column(name="contact_data",   data_type="dict")
COL_CT_CREATED_AT         = Column(name="created_at",     data_type="datetime")
COL_CT_UPDATED_AT         = Column(name="updated_at",     data_type="datetime")

ALL_CT_COL = [COL_ID,
              COL_CT_KEY,
              COL_CT_ADDRESSBOOK_KEY,
              COL_CT_UID,
              COL_CT_KIND,
              COL_CT_LAST_NAME,
              COL_CT_FIRST_NAME,
              COL_CT_ORGANIZATION,
              COL_CT_DISPLAY_NAME,
              COL_CT_IS_DELETED,
              COL_CT_SEARCH_VECTOR,
              COL_CT_CONTACT_DATA,
              COL_CT_CREATED_AT,
              COL_CT_UPDATED_AT]

IDX_CT_ADDRESSBOOK_KEY = Index(name="idx_ct_addressbook_key", columns=(COL_CT_ADDRESSBOOK_KEY.name,))
IDX_CT_UID = Index(name="idx_ct_uid", columns=(COL_CT_UID.name,))
IDX_CT_SORT = Index(name="idx_ct_sort", columns=(COL_CT_ADDRESSBOOK_KEY.name, COL_CT_LAST_NAME.name, COL_CT_FIRST_NAME.name))
# Dedicated full-text structure: GIN on the tsvector column (PostgreSQL) / FULLTEXT on the TEXT column (MariaDB).
IDX_CT_SEARCH = Index(name="idx_ct_search_vector", columns=(COL_CT_SEARCH_VECTOR.name,), fulltext=True)

TABLE_CONTACT = Table(name=process_config.SOGO_P_TABLE_CONTACTS, columns=ALL_CT_COL,
                      primary_keys=(COL_ID.name, COL_CT_KEY.name),
                      indexes=[IDX_CT_ADDRESSBOOK_KEY, IDX_CT_UID, IDX_CT_SORT, IDX_CT_SEARCH])

#############################
# Table sogo6_contacts_lists #
#############################
"""
Stores distribution lists (vCard KIND:group, RFC 6350 6.1.4). A list belongs to one address book,
like a contact, and is the object members are attached to. Members themselves live in the join table
sogo6_contacts_list_members and are plain references to contacts (modify-propagates).

Key queries:
  SELECT ... FROM sogo6_contacts_lists WHERE addressbook_key = ? AND is_deleted = FALSE ORDER BY name
"""
# key: opaque token exposed in the API instead of id, like contacts and address books
# addressbook_key: key of the owning address book - nullable so the row survives the book's deletion
# uid: vCard UID - the stable identity carried in the .vcf and matched across CardDAV sync (RFC 6352);
#   dormant while the API is REST only, used by the KIND:group serializer
# name: display name of the list
# description: optional free-text description, nullable
# is_deleted: soft delete flag - never DELETE FROM (required for CardDAV sync reports)
# created_at / updated_at: UTC timestamps
COL_LST_KEY               = Column(name="key",            data_type="str",      is_unique=True,                    extra_args={"max_len": 64})
COL_LST_ADDRESSBOOK_KEY   = Column(name="addressbook_key", data_type="str",      is_nullable=True,                  extra_args={"max_len": 64})
COL_LST_UID               = Column(name="uid",            data_type="str",                                         extra_args={"max_len": 512})
COL_LST_NAME              = Column(name="name",           data_type="str",                                         extra_args={"max_len": 255})
COL_LST_DESCRIPTION       = Column(name="description",    data_type="text",     is_nullable=True)
COL_LST_IS_DELETED        = Column(name="is_deleted",     data_type="bool")
COL_LST_CREATED_AT        = Column(name="created_at",     data_type="datetime")
COL_LST_UPDATED_AT        = Column(name="updated_at",     data_type="datetime")

ALL_LST_COL = [COL_ID,
               COL_LST_KEY,
               COL_LST_ADDRESSBOOK_KEY,
               COL_LST_UID,
               COL_LST_NAME,
               COL_LST_DESCRIPTION,
               COL_LST_IS_DELETED,
               COL_LST_CREATED_AT,
               COL_LST_UPDATED_AT]

IDX_LST_ADDRESSBOOK_KEY = Index(name="idx_lst_addressbook_key", columns=(COL_LST_ADDRESSBOOK_KEY.name,))
IDX_LST_UID = Index(name="idx_lst_uid", columns=(COL_LST_UID.name,))

TABLE_CONTACT_LIST = Table(name=process_config.SOGO_P_TABLE_CONTACT_LISTS, columns=ALL_LST_COL,
                           primary_keys=(COL_ID.name, COL_LST_KEY.name),
                           indexes=[IDX_LST_ADDRESSBOOK_KEY, IDX_LST_UID])

####################################
# Table sogo6_contacts_list_members #
####################################
"""
Join table between a distribution list and its member contacts (N:M). A member is a reference to a
contact, never an ad-hoc email, so editing the contact propagates to every list it belongs to.
Both ends are referenced by their opaque key, consistent with the rest of the schema (contacts
reference their book by addressbook_key, events reference their calendar by key) - never by the
internal id. A member must be a contact of the list's own address book (enforced by the service
layer); the join carries no book column.

Key queries:
  SELECT contact_key FROM sogo6_contacts_list_members WHERE list_key = ?            (expand a list)
  SELECT list_key    FROM sogo6_contacts_list_members WHERE contact_key = ?         (lists of a contact)
"""
# list_key: key of the owning list (sogo6_contacts_lists.key)
# contact_key: key of the member contact (sogo6_contacts_contacts.key)
COL_LM_LIST_KEY           = Column(name="list_key",      data_type="str",                                         extra_args={"max_len": 64})
COL_LM_CONTACT_KEY        = Column(name="contact_key",   data_type="str",                                         extra_args={"max_len": 64})

ALL_LM_COL = [COL_LM_LIST_KEY,
              COL_LM_CONTACT_KEY]

IDX_LM_CONTACT_KEY = Index(name="idx_lm_contact_key", columns=(COL_LM_CONTACT_KEY.name,))

TABLE_CONTACT_LIST_MEMBER = Table(name=process_config.SOGO_P_TABLE_CONTACT_LIST_MEMBERS, columns=ALL_LM_COL,
                                  primary_keys=(COL_LM_LIST_KEY.name, COL_LM_CONTACT_KEY.name),
                                  indexes=[IDX_LM_CONTACT_KEY])

###########################
# Table sogo6_file_storage #
###########################
"""
Generic binary blob store keyed by an opaque key. Decouples large binary payloads (e.g. contact
photos) from the rows that reference them, so a listing never loads the bytes. The referencing row
keeps only the key; the bytes and their MIME type are fetched on demand.
"""
# key: opaque token referenced by the owning row (e.g. a contact photo entry)
# data: the raw bytes (bytea / LONGBLOB)
# content_type: the MIME type, needed to rebuild a data: URI on read
# content_hash: sha256 hex of the bytes, to compare content without loading the blob
# created_at / updated_at: UTC timestamps
COL_FS_KEY                = Column(name="key",          data_type="str",   is_unique=True,  extra_args={"max_len": 64})
COL_FS_SOURCE             = Column(name="source",       data_type="str",                    extra_args={"max_len": 32})
COL_FS_DATA               = Column(name="data",         data_type="bytes")
COL_FS_CONTENT_TYPE       = Column(name="content_type", data_type="str",                    extra_args={"max_len": 128})
COL_FS_CONTENT_HASH       = Column(name="content_hash", data_type="str",                    extra_args={"max_len": 64})
COL_FS_CREATED_AT         = Column(name="created_at",   data_type="datetime")
COL_FS_UPDATED_AT         = Column(name="updated_at",   data_type="datetime")

ALL_FS_COL = [COL_FS_KEY,
              COL_FS_SOURCE,
              COL_FS_DATA,
              COL_FS_CONTENT_TYPE,
              COL_FS_CONTENT_HASH,
              COL_FS_CREATED_AT,
              COL_FS_UPDATED_AT]

TABLE_FILE_STORAGE = Table(name=process_config.SOGO_P_TABLE_FILE_STORAGE, columns=ALL_FS_COL, primary_keys=(COL_FS_KEY.name,))

##############################
# Table tmp_draft      #
##############################
"""
Temporary table tracking draft state for mail operations.
Prevents concurrent modifications on the same draft.

Key queries:
  SELECT ... FROM tmp_draft WHERE owner = ?
  SELECT ... FROM tmp_draft WHERE key = ?
"""
# key: opaque unique hash identifying this draft state entry
# owner: uid of the user owning the draft — FK to sogo_user_profiles.uid — indexed for per-user queries
# mail_server_uid: uid used to locate the Draft on the mail server
# lock_state: True means a request is currently modifying the Draft; other operations must wait
# headers: JSON blob reserved for future use (e.g. custom mail headers set by the client before sending)
# last_updated: Unix timestamp (seconds since epoch) updated on every insert/modify of this entry
COL_DRAFT_KEY             = Column(name="key",             data_type="str",  is_unique=True, extra_args={"max_len": 64})
COL_DRAFT_OWNER           = Column(name="owner",           data_type="str",                  extra_args={"max_len": 512})
COL_DRAFT_MAIL_SERVER_UID = Column(name="mail_server_uid", data_type="str",                  extra_args={"max_len": 512})
COL_DRAFT_LOCK_STATE      = Column(name="lock_state",      data_type="bool")
COL_DRAFT_HEADERS         = Column(name="headers",         data_type="dict", is_nullable=True)
COL_DRAFT_LAST_UPDATED    = Column(name="last_updated",    data_type="int",  is_nullable=True)

ALL_DRAFT_COL = [COL_ID,
                 COL_DRAFT_KEY,
                 COL_DRAFT_OWNER,
                 COL_DRAFT_MAIL_SERVER_UID,
                 COL_DRAFT_LOCK_STATE,
                 COL_DRAFT_HEADERS,
                 COL_DRAFT_LAST_UPDATED]

IDX_DRAFT_OWNER = Index(name="idx_draft_owner", columns=(COL_DRAFT_OWNER.name,))

TABLE_DRAFT_STATE = Table(name=process_config.SOGO_P_TABLE_TMP_DRAFTS, columns=ALL_DRAFT_COL, primary_keys=(COL_ID.name, COL_DRAFT_KEY.name),
                          indexes=[IDX_DRAFT_OWNER])

ALL_TABLES = [TABLE_SETTINGS,
              TABLE_DOMAIN,
              TABLE_RULES,
              TABLE_USER,
              TABLE_CALENDAR,
              TABLE_EVENT,
              TABLE_REMINDER,
              TABLE_ADDRESSBOOK,
              TABLE_CONTACT,
              TABLE_CONTACT_LIST,
              TABLE_CONTACT_LIST_MEMBER,
              TABLE_FILE_STORAGE,
              TABLE_DRAFT_STATE]
