
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

JWT_ISS = "iss"
JWT_EXP = "exp"

#TTL
TTL_1D = 86400
TTL_1H =  3600
TTL_5M =   300

# SOGo ACL Rights - Field names for rights dictionaries
USERCANVIEWFOLDER = "userCanViewFolder"
USERCANREADMAILS = "userCanReadMails"
USERCANMARKMAILSREAD = "userCanMarkMailsRead"
USERCANINSERTMAILS = "userCanInsertMails"
USERCANPOSTMAILS = "userCanPostMails"
USERCANCREATESUBFOLDERS = "userCanCreateSubfolders"
USERCANREMOVEFOLDER = "userCanRemoveFolder"
USERCANERASEMAILS = "userCanEraseMails"
USERCANEXPUNGEFOLDER = "userCanExpungeFolder"
USERCANWRITEMAILS = "userCanWriteMails"
USERCANADMINISTRATOR = "userIsAdministrator"