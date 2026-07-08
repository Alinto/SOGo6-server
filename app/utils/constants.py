
#SOGO_STATE
SOGO_UNDEFINED = -1 #Sogo has not run its init method yet
SOGO_NOT_OK    = 0 #Sogo can't run properly. Problems with database, redis or agent
SOGO_NOT_INIT  = 1 #Sogo can run but has no system or defaul_domain settings (first installation)
SOGO_OK        = 2 #Sogo can run properly

#App conf
ALLOW_AUTH_BASIC = "ALLOW_AUTH_BASIC"
ALLOW_AUTH_NO_CHECK = "ALLOW_AUTH_NO_CHECK"


#API kind
API_BASIC = "user" #Api for all users
API_ADMIN = "admin" #Api for admin

#LOGIN, USER SESSION, VOUCHER
USER_UID    = "uid"
USER_PWD    = "password"
USER_DOMAIN = "domain"
USER_EMAIL  = "email"
USER_SRC_ID = "source_id"
USER_CN     = "cn"
SESSION_KEY = "session_key"
SESSION_LAST_SEEN = "last_activity"
SESSION_SENSITIVE = "sensitive_data"

USER_CLASS_USER  = "user"      #Simple user
USER_CLASS_GROUP = "group"     #Group of one or sevral users
USER_CLASS_RES   = "ressource" #Ressource, location, room, things...
USER_CLASS_ANY   = "anyone"    #Anyone (and anything) that can be authenticated
USER_CLASS_ANON  = "anonymous"
# Sorted set used to index user sessions by last activity timestamp.
# Each member is a ``user_session:<uuid>`` key and its score is the
# Unix timestamp of the last activity.
ZSET_USER_SESSIONS_ACTIVITY = "user_sessions:activity"
# Sorted set used to index user sessions by uid (lexicographic score).
# Each member is a ``user_session:<uuid>`` key and its score is derived
# from the uid string so that sessions can be sorted / filtered by uid.
ZSET_USER_SESSIONS_UID = "user_sessions:uid"
# Sorted set used to index user sessions by domain (lexicographic score).
# Each member is a ``user_session:<uuid>`` key and its score is derived
# from the domain string so that sessions can be sorted / filtered by domain.
ZSET_USER_SESSIONS_DOMAIN = "user_sessions:domain"

JWT_ISS = "iss"
JWT_EXP = "exp"

# ACCOUNT AND IDENTITY
DEFAULT_IDENTITY_KEY_VALUE = "0"

# SOCKET ENCRYPTION
SOCKET_ENC_PLAIN = "None"
SOCKET_ENC_IMPLICIT_TLS = "SSL/TLS"
SOCKET_ENC_EXPLICIT_TLS = "StartTLS"
SOCK_ENC_LIST = (SOCKET_ENC_PLAIN, SOCKET_ENC_IMPLICIT_TLS, SOCKET_ENC_EXPLICIT_TLS)

#MAIL_SERVER_FOLDER_TYPE
MAIL_FOLDER_INBOX    = "INBOX"    #Folder made to store incoming mail if no filters
MAIL_FOLDER_SENT     = "SENT"     #Folder made to store mail sent
MAIL_FOLDER_DRAFT    = "DRAFT"    #Folder made to store mail not already sent
MAIL_FOLDER_JUNK     = "JUNK"     #Folder made to store mail viewed as SPAM
MAIL_FOLDER_TRASH    = "TRASH"    #Folder made to store deleted mail before permanent deletion
MAIL_FOLDER_TEMPLATE = "TEMPLATE" #Folder made to store tamplate mail
MAIL_FOLDER_PLANNED  = "PLANNED"  #Folder made to store mail planned to be sent later
MAIL_FOLDER_NORMAL   = "NORMAL"   #Folder with no special used except to store mails


#IMAP
IMAP_DEFAULT_DELIMITER = "/./." #It will be a key (not the value) to get the default delimiter of all namespaces.
                                #the strange key value is just to make sure it won't overwritte a real prefix name (see ClientImap.py)

#TTL
TTL_1D = 86400
TTL_1H =  3600
TTL_5M =   300

# HTTP LIMITS
# Hard cap on the HTTP request body size, wired into Flask's MAX_CONTENT_LENGTH at startup.
# Rejects oversized uploads (e.g. calendar .ics imports) at the WSGI layer before any
# application code reads the body into memory. Per-route limits (e.g. MAX_IMPORT_ICS_BYTES)
# should always be smaller than this cap; raise this value when a module needs to accept
# bigger payloads.
MAX_HTTP_REQUEST_BYTES = 10 * 1024 * 1024 + 64 * 1024  # 10 MB + multipart framing overhead

# SOGo ACL Rights - Field names for rights dictionaries
USER_CAN_VIEW_FOLDER = "userCanViewFolder"
USER_CAN_READ_MAILS = "userCanReadMails"
USER_CAN_MARK_MAILS_READ = "userCanMarkMailsRead"
USER_CAN_INSERT_MAILS = "userCanInsertMails"
USER_CAN_POST_MAILS = "userCanPostMails"
USER_CAN_CREATE_SUBFOLDERS = "userCanCreateSubfolders"
USER_CAN_REMOVE_FOLDER = "userCanRemoveFolder"
USER_CAN_ERASE_MAILS = "userCanEraseMails"
USER_CAN_EXPUNGE_FOLDER = "userCanExpungeFolder"
USER_CAN_WRITE_EMAILS = "userCanWriteMails"
USER_CAN_ADMINISTRATOR = "userIsAdministrator"

# SOGO API MAIl KEYS
FOLDER_NAME = "name"
FOLDER_PATH = "path"
FOLDER_URL_PATH = "url_path"
FOLDER_DELIMITER = "delimiter"
FOLDER_FILTER_PATH = "filter_path"
FOLDER_TYPE = "type"
FOLDER_FLAGS = "flags"
FOLDER_CHILDREN = "children"
FOLDER_SELECTABLE = "selectable"
FOLDER_SUSBCRIBED = "subscribed"
FOLDER_UNSEEN = "unseen_count"
FOLDER_COUNT = "message_count"

# tmp_draft
TMP_DRAFT_KEY_SIZE = 32  # Length of the unique hash key for a tmp_draft entry

# Mail deletion behavior mapping to (move_to_trash, permanently) flags
DELETE_MAIL_BEHAVIOR_MAP = {
    # behavior                   move_to_trash  permanently
    "MOVE_TO_TRASH_AND_EXPUNGE": (True,         True),
    "FLAG_DELETED_ONLY":         (False,        False),
    "EXPUNGE_ONLY":              (False,        True),
    "MOVE_TO_TRASH_ONLY":        (True,         False),
}

FILTER_SECTION_FILTERS: str = "filters"
FILTER_SECTION_VACATION: str = "vacation"
FILTER_SECTION_FORWARD: str = "forward"
FILTER_SECTION_NOTIFICATION: str = "notification"

# All sections that are pushed to the Sieve server as a merged script.
FILTER_SECTIONS: tuple[str, ...] = (
    FILTER_SECTION_FILTERS,
    FILTER_SECTION_VACATION,
    FILTER_SECTION_FORWARD,
    FILTER_SECTION_NOTIFICATION,
)

FILTER_FIELD_SUBJECT  = "subject"
FILTER_FIELD_FROM     = "from"
FILTER_FIELD_TO       = "to"
FILTER_FIELD_CC       = "cc"
FILTER_FIELD_TO_OR_CC = "to or cc"
FILTER_FIELD_HEADER   = "header"
FILTER_FIELD_BODY     = "body"
FILTER_FIELD_SIZE     = "size"

FILTER_OP_IS           = "is"          #exactly is
FILTER_OP_IS_NOT       = "notis"       #exactly is not
FILTER_OP_CONTAINS     = "contains"    #contains
FILTER_OP_CONTAINS_NOT = "notcontains" #does not contain
FILTER_OP_MATCHES      = "matches"     #Like is but permissive (dog will march DoG, dogs, Dog...)
FILTER_OP_MATCHES_NOT  = "notmatches"  
FILTER_OP_REGEX        = "regex"       #regex
FILTER_OP_REGEX_NOT    = "notregex"
FILTER_OP_EXISTS       = "exists"      #for field FILTER_FIELD_HEADER, does exist
FILTER_OP_EXISTS_NOT   = "notexists"
FILTER_OP_OVER         = "over"        #for field FILTER_FIELD_SIZE (size of the mail)
FILTER_OP_UNDER        = "under"

FILTER_ACTION_FILEINTO = "fileinto"
FILTER_ACTION_REDIRECT = "redirect"
FILTER_ACTION_REJECT   = "reject"
FILTER_ACTION_DISCARD  = "discard"
FILTER_ACTION_KEEP     = "keep"
FILTER_ACTION_FLAG     = "addflag"
FILTER_ACTION_NOTIFY   = "notify"
FILTER_ACTION_STOP     = "stop"

#LDAP
LDAP_SCOPE_BASE = "BASE"
LDAP_SCOPE_ONE  = "ONE"
LDAP_SCOPE_SUB  = "SUB"
