
#SOGO_STATE
SOGO_NOT_OK   = 0 #Sogo can't run properly. Problems with database, redis or agent
SOGO_NOT_INIT = 1 #Sogo can run but has no system or defaul_domain settings (first installation)
SOGO_OK       = 2 #Sogo can run properly

#API kind
API_BASIC = "user" #Api for all users
API_ADMIN = "admin" #Api for admin

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
