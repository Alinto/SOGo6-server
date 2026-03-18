
#SOGO_STATE
SOGO_NOT_OK   = 0 #Sogo can't run properly. Problems with database, redis or agent
SOGO_NOT_INIT = 1 #Sogo can run but has no system or defaul_domain settings (first installation)
SOGO_OK       = 2 #Sogo can run properly

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
MAIL_FOLDER_NORMAL   = "NORMAL"   #Folder with no special used except to store mails

#IMAP
IMAP_DEFAULT_DELIMITER = "/./." #It will be a key (not the value) to get the default delimiter of all namespaces.
                                #the strange key value is just to make sure it won't overwritte a real prefix name (see ClientImap.py)

#TTL
TTL_1D = 86400
TTL_1H =  3600
TTL_5M =   300

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
FOLDER_FILTER_PATH = "filterPath"
FOLDER_TYPE = "type"
FOLDER_FLAGS = "flags"
FOLDER_CHILDREN = "children"
FOLDER_SELECTABLE = "selectable"
FOLDER_SUSBCRIBED = "subscribed"
FOLDER_UNSEEN = "unseenCount"
FOLDER_COUNT = "messageCount"
