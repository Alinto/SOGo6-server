# -*- coding: utf-8 -*-

"""
This file contains dictionnary matching the SOGo 5 parameters to SOGo 6 parameters adn vice-versa
"""

#Tip: 256 means 5 to 6. 625 means 6 to 5
#Tip: A value of None means the settings is either irrvelant or handle by something else
#Tip: The bible of SOGo 5 is here -> https://www.sogo.nu/files/docs/SOGoInstallationGuide.html

system_526 = {
    # Authentication by sogo settings, now domains settings to allow making method by domain.
    "SOGoAuthenticationType": "SOGO_D_AUTH_TYPE", # Now this is a domain parameter, see DomainSettings

        #Auth Cas settings
        "SOGoCASServiceURL":      "SOGO_D_CAS_URL",
        "SOGoCASLogoutEnabled":   "SOGO_D_CAS_LOGOUT_ENABLED",

        #Auth SAML2 settings
        "SOGoSAML2CertificateLocation":    "",    #TODO but first, undesrtand the saml2 protocol...
        "SOGoSAML2IdpCertificateLocation": "",
        "SOGoSAML2IdpMetadataLocation":    "",
        "SOGoSAML2IdpPublicKeyLocation":   "",
        "SOGoSAML2LoginAttribute":         "",
        "SOGoSAML2LogoutEnabled":          "",
        "SOGoSAML2LogoutURL":              "",
        "SOGoSAML2PrivateKeyLocation":     "",

        #Auth OpenId
        "OCSOpenIdURL":                 None, #This table is no more needed in SOGo6
        "SOGoOpenIdConfigUrl":          "SOGO_D_OPENID_CONFIG_URL", #contains the well-known configuration like https://myopenid.net/.well-known/openid-configuration
        "SOGoOpenIdClient":             "SOGO_D_OPENID_CLIENT_NAME", #Name of the openid client
        "SOGoOpenIdClientSecret":       "SOGO_D_OPENID_CLIENT_SECRET", #Secret of the openid client
        "SOGoOpenIdScope":              "SOGO_D_OPENID_SCOPE", #Scope of the openid client
        "SOGoOpenIdEmailParam":         "SOGO_D_OPENID_EMAIL", #Paramester from USerProfile that contains the mail of the user
        "SOGoOpenIdEnableRefreshToken": None, #autodetected by sogo 6
        "SOGoOpenIdTokenCheckInterval": "SOGO_D_OPENID_TOKEN_CHECK_INTERVAL", #Once the token is check valid, don't do it for this number of seconds
        "SOGoOpenIdLogoutEnabled":      None, #Autodetected by sogo

    # Authentication made by a proxy and sogo trust it
    "SOGoTrustProxyAuthentication": "", #TODO see backArchi info in Authentication chapter
    "SOGoEncryptionKey":            "",

    # Cache system, change from memcached to redis
    "SOGoCacheCleanupInterval": "SOGO_P_REDIS_TTL", # ENV, but do we set it for all params????
    "SOGoMemcachedHost":        None, # Redis is used now, see SOGO_P_REDIS_URL.


    # Calendar Settings
    "SOGoCalendarEnableJitsiLink": "SOGO_D_JITSI_LINK_ENABLED", #Move to domain, careful default value was False and is now True
                                                                #Also see SOGoCalendarJitsiBaseUrl in domain_526

    # DAV settings, now is domain
    "SOGoAddressBookDAVAccessEnabled": "SOGO_D_CARDAV_ENABLED",
    "SOGoCalendarDAVAccessEnabled":    "SOGO_D_CALDAV_ENABLED",

    # Language
    "SOGoSupportedLanguages": None, #TODO, To limit the languages available for users (SOGoLanguage). Useless and not inclusive.

    # Logging
    "WOLogFile": None, # The logfile path is fixed in SOGo 6

    #Login
    "SOGoMaximumFailedLoginCount":    "SOGO_D_LOGIN_CHECK_MAX_ATTEMPT", #Logic to block user an amount of time after too many fails attempt.
    "SOGoMaximumFailedLoginInterval": "SOGO_D_LOGIN_CHECK_TIME_SPAN",   #Add a parameter in SOGo 6 to enbale it  See SOGO_D_LOGIN_CHECK_FAIL
    "SOGoFailedLoginBlockInterval":   "SOGO_D_LOGIN_CHECK_BLOCK_TIME",

    "SOGoForbidUnknownDomainsAuth": "SOGO_S_REJECT_UNKNOWN_DOMAIN", #If domains have been defined in sogo, forbid any logi nrequest without a correct domain
    "SOGoDomainAllowed":            "SOGO_S_KNOWN_DOMAIN", #If domains have not been defined, list them here to use SOGoForbidUnknownDomainsAuth

    #Multi-domain
    "SOGoEnableDomainBasedUID": None, #TODO Not needed anymore, force user to login with the full email.
    "SOGoLoginDomains": None, #TODO list of domains the user can choose from when login. Still usefull?
    "SOGoDomainsVisibility": None, #TODO was used to tell which domain can wee which, is refactored in SOGo 6.

    #Mailing - Those parameters are also set byt the SMTP server, but it tells sogo how to act before actually requetsing the smtp server
    "SOGoMaximumMessageSubmissionCount":  "SOGO_D_MAIL_MAX_SUBMISSION", #Maximum mail an user san send during SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL
    "SOGoMaximumRecipientCount":          "SOGO_D_MAIL_MAX_RECIPIENT", #Maximum recepient allowed by SOGo
    "SOGoMaximumSubmissionInterval":      "SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL", #Interval for SOGO_D_MAIL_MAX_SUBMISSION
    "SOGoMessageSubmissionBlockInterval": "SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl", #Number of seoncds when a user is forbid to send mail after SOGO_D_MAIL_MAX_SUBMISSION

    #Mailing - only sogo for this one
    "SOGoEnableMailCleaning": "SOGO_D_MAIL_ALLOW_PURGE", #Allow or not users to purge their folders (clean all before a date) BEware default value change

    #Alarms
    "SOGoEnableEMailAlarms": "SOGO_D_REMINDER_ALLOW_MAIL", #Allow the users of this domain to set mail reminder

    #CALDAV
    "SOGoDisableOrganizerEventCheck": "SOGO_U_DAV_FORCE_SYNC_FROM_CLIENT", #If the event is already in the database and caldav push the same event in a previous version
                                                                           #(sequence id) overwrite it. #TODO check this behaviour

    #Binary
    "WOSendMail": "SOGO_S_SENDMAIL", #Path of the sendmail binary
    "SOGoZipPath": None, #It's python who does it itself.

    #Passwords
    "SOGoPasswordRecoveryEnabled": "SOGO_D_PWD_RECOVERY", #Allow user to set a method to recover passwords. Was a system  param, now domains
    "SOGoPasswordRecoveryDomains": None, #Allow domains that enable password recovery if SOGoPasswordRecoveryEnabled is not set
                                         #Now that SOGO_D_PWD_RECOVERY is a domain param instead, no need of this one anymore

    "SOGoJWTSecret": None, #Token used to encrypt/decrypt word used in secondary email passsword recovery. No need to migrate this secret

    # Process/Memory settings, now handle by gunicorn/docker/kubernetes
    "SxVMemLimit":    None, # Managed by kubernetes or container
    "WOPidFile":      None, # Non-revelant for SOGo 6, managed by gunicorn/flask
    "WOWorkersCount": None, # Non-revelant for SOGo 6, manages by Gunicorn setting 'workers'

    #Secret
    "SOGoSecretType": None, #In SOGo, secret to encrypt/decrypt sensitive data, this param was telling if the secret is in sogo.conf or an ENV.
                            #In SOGo6 secre will mandatory be ENV
    "SOGoSecretValue": "SOGO_P_SECRET", #Was optionnal in SOGo5, now mandatory to start the application. Encrypt/decrypt sensitive data with AED-GCM-256

    # Webserver settings, now handle by flask/gunicorn
    "SOGoMaximumMessageSizeLimit": None, # see WOMaxUploadSize
    "WOListenQueueSize":           None, # Value shouldn't be migrated because new techno. Gunicorn setting 'backlog'
    "WOMaxUploadSize":             None, # See MAX_CONTENT_LENGTH, MAX_FORM_MEMORY_SIZE, MAX_FORM_PARTS
                                         # for flask https://flask.palletsprojects.com/en/stable/config/
                                         # and for gunicorn https://docs.gunicorn.org/en/stable/settings.html#security
    "WOPort":                      None, # Do not migrate. For flask options --port. For Gunicorn, see setting 'bind'
    "WOWatchDogRequestTimeout":    None, # Do not migrate. Set by gunicorn settings 'timeout'

    "SOGoMaximumRequestCount" :   "SOGO_D_API_MAX_REQUEST",           #Limit request from the same user (user indeed, not the ip) during SOGoMaximumRequestInterval seconds
    "SOGoMaximumRequestInterval": "SOGO_D_API_MAX_REQUEST_INTERVAL",  #Then block user for SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL seconds
    "SOGoRequestBlockInterval":   "SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL",

    "SOGoXSRFValidationEnabled": None, # XSRF protection should be enable by default but there's probkem with flask-wtf as we only are a api server
                                       #see https://stackoverflow.com/questions/76495115/flask-wtf-generate-token-manually-in-routes

    "SOGoURLEncryptionEnabled":    None, #feat added to hide the mail in the url of sgo webmail. We wo'nt do that in SOGo 6 so useless.
    "SOGoURLEncryptionPassphrase": None, #Was used for above feat, not needed anymore

    #Web configuration #TODO see with front
    "SOGoPageTitle": None, #TODO change the html head <title> -> move to Front config?
    "SOGoHelpURL": "", #Add a button that redirect to a help webpage
    "SOGoFaviconRelativeURL": None, #Defined the favicon path. Why bother...


}

domain_526 = {

    # Admin
    "SOGoSuperUsernames":         None, #TODO, there is rework of admin users and what they can do.
    "SOGoPasswordChangeEnabled": "SOGO_D_PWD_CHANGE_ENABLED", #Allow users to change the password (for ldap it means the ldap admin account is allow to do that too)
    "SOGoUIAdditionalJSFiles": None, #TODO SOGo 5 allow admin to add js file. Mainly to change the theme.jsbut I know others people have use of that...
    "SOGoUIxAdditionalPreferences": None, #Not used in SOGo 5

    # Mail settings
    "SOGoSubscriptionFolderFormat": None, #Allowed to format the name of the susbcribed mail folders. Not necessary because: too much customization.
    "SOGoMailJunkSettings": "SOGO_D_MAIL_JUNK_SETTINGS", #TODO see with alinto the best way to do this.
                                                        #SOGoMailJunkSettings = {
                                                        # 	vendor = "generic";
                                                        # 	junkEmailAddress = "spam@foo.com";
                                                        # 	notJunkEmailAddress = "ham@foo.com";
                                                        # 	limit = 10;
                                                        # };
    "SOGoMailKeepDraftsAfterSend": None, #TODO to keep?

    # Calendar Settings
    "SOGoAppointmentSendEMailNotifications": None, #TODO Is it useful? To forbid user to send update to others when modifying event
                                                   #It should be a choice when the user modify the event.
                                                   #I see a case where sogo is only used for calendar sharing and does not have a smtp server...
    "SOGoCalendarDefaultRoles":          None, #Determines the 'default' acl of a user when opening the share view. Useless
    "SOGoCalendarJitsiBaseUrl":          "SOGO_D_JITSI_BASE_URL", #See SOGoCalendarEnableJitsiLink in system_526
    "SOGoCalendarJitsiRoomPrefix":       None, #Merge with SOGO_D_JITSI_BASE_URL = SOGoCalendarJitsiBaseUrl + SOGoCalendarJitsiRoomPrefix
    "SOGoHideSystemEMail":               None, #Hide the true value for calendar-user-address-set DAV param. No need and no info on that on internet. 
    "SOGoiPhoneForceAllDayTransparency": None, #Made in 2010 to force allDay event coming from iphone to be transparent for freebusy, irrelevant today.
    "SOGoNotifyOnPersonalModifications": None, #Useless as user can ovveride it in calendar property
    "SOGoNotifyOnExternalModifications": None, #Useless as user can ovveride it in calendar property
    "SOGoFreeBusyDefaultInterval": None, #TODO was telling the span of freebusy evaluated for events (default to (-7,+7 days)).
                                         #Depends on how the front can manage the calendar view but we can make one week + boutton to go to the next or previous week.
                                         #So a fixed lenghts of 7 days.
    "SOGoDAVCalendarStartTimeLimit": "SOGO_D_DAV_START_TIME", #Limit the numbers of days that caldav sync in the past. Default to 0, no limit.
                                                                 #Example: 180 means caldav only returns events that are less than 180 days old.

    # Contact setting
    "SOGoContactsDefaultRoles": None, #Determines the 'default' acl of a user when opening the share view. Useless

    # Folder settings
    "SOGoACLsSendEMailNotifications":    None, #TODO It should be mandatory to tell user when they now have rights on another folder.
    "SOGoDisableExport":                 "SOGO_D_FOLDER_DISABLE_EXPORT", #Disable sharing of folders (remove the uppercase for value)
    "SOGoDisableSharing":                "SOGO_D_FOLDER_DISABLE_SHARING", #Disable sharing of folders (remove the uppercase for value)
    "SOGoDisableSharingAnyAuthUser":     "SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH", #Disable sharing for any authenticated user (remove the uppercase for value)
    "SOGoEnablePublicAccess":            "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE", #Enable public acces to dav link #TODO, seperate in two settings SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE

    "SOGoFoldersSendEMailNotifications": "SOGO_U_FOLDER_CREATION_NOTIF", #Was domain but better at user's, change the default from False to True
    "SOGoSearchMinimumWordLength":       "SOGO_D_AUTOCOMPLETION_MIN_LEN", #Minimum length of chars before searching for autocompletion

    #Imap Identities
    "SOGoCreateIdentitiesDisabled": "SOGO_D_IDENTITIES_ENABLED", #Allow user to create identities (from, reply-to, name, signature)
                                                                 #Behavior change in SOGo 6 as it is disabled by default #TODO
    "SOGoMailCustomFromEnabled": "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED", #ALlow user to change their mail in their identities 

    # LDAP
    "SOGoLDAPContactInfoAttribute": None, #TODO Move to US_EXTRA_CONTACT_INFO

    # Mail Editor
    "SOGoForceRawHtmlSignature": None, #SHould be set to YES in our case (value by default in SOGo5) -> https://bugs.sogo.nu/view.php?id=5920
                                       #Needs work on CKeditor in SOGo6 to fully undesrtand it.

    # Mailing
    "SOGoMailDomain":          None, #Not even use in SOGo 5...  
    "SOGoMailDisableXForward": None, #SOGo 5 automatically added an header X-Forward with the nginx custom sogo
                                     #x-webobjects-remote-host ip, not necessary? #TODO ask exploit
    "SOGoForceExternalLoginWithEmail": None, #Force user to use the mail instead of its uid for imap/smtp auth. #TODO,
                                             #Clearly put in config what to use for imap/smtp uid? cn? mail?
                                             #Keep in mind this is also a smtp/imap config.
    "SOGoSoftQuotaRatio": "SOGO_D_SOFT_EMAIL_QUOTA", #Lie to your users by telling them there are less quota that avaiable.
                                                     #To avoid them to overflow the quota so you could act before.
                                                     #Value in ]0;1], percentage to the true quota
    "SOGoMailUseOutlookStyleReplies": None, #Not used by SOGo 5
    "SOGoMailListViewColumnsOrder": None, #Not used by SOGo 5
    "SOGoMailCertificateEnabled": None, #Allow or not to add s/mime certificat for itself. #TODO Why on earth we will forbid user to do that?

    # Password
    "SOGoPasswordRecoveryFrom": "SOGO_D_MAIL_SYSTEM_FROM", #Nothing to do with imap, mail used as from for sending email recovery's password.
                                                           #Diff with SOGoSMTPMasterUserUsername is this is not a user email.
                                                           #default is noreply@<domain> or the string "domain" if not defined
                                                           #btw this doesn't work if smtp forces auth because sogo won't

    #User source
    "SOGoUserSources": "SOGO_D_USERSOURCE",

    #Outoing Server
    "SOGoMailingMechanism": "SOGO_D_MAIL_OUTGOING_TYPE",          #type ot the mechanism to send mail: sendmail or smtp
    "SOGoSMTPServer": "SOGO_D_SMTP_SERVER",                   #hostname/url of the smtp server can be from smtp://domain:port to the domain only
                                                              #To simplify thing, we add others params as SOGO_D_SMTP_PORT and SOGO_D_SMTP_ENCRYPTION
    "SOGoSMTPAuthenticationType": "SOGO_D_SMTP_AUTH_MECH",    #auth mechanism of the smtp server null (no auth), plain or xoauth2
    "SOGoSMTPMasterUserEnabled":"SOGO_D_SMTP_MASTER_ENABLED", #For system message (notificaitons, invit...) use a master account instead of the user.
    "SOGoSMTPMasterUserUsername":"SOGO_D_SMTP_MASTER_LOGIN",   #Master mail
    "SOGoSMTPMasterUserPassword":"SOGO_D_SMTP_MASTER_PWD",    #Master password

    #Ingoing Server
    "NGImap4AuthMechanism": "SOGO_D_IMAP_AUTH_MECH", #auth mechanism for imap
    "SOGoIMAPCASServiceName" : None, #Not sure how useful it is. SOGo 5 guide says it has to do with pam_cas.
    "SOGoIMAPServer": "SOGO_D_IMAP_SERVER", #IMAP hostname will be simpligy with others param SOGO_D_IMAP_PORT and SOGO_D_IMAP_ENCRYPTION
    "SOGoSieveServer": "SOGO_D_SIEVE_SERVER", #Same but for sieve (#TODO can a sieve server be different than the imap one?)
    "SOGoSieveFolderEncoding": "SOGO_D_SIEVE_FOLDER_ENCODING", #apparently, imap and sieve use UTF7 to encode their folder name.
                                                               #This param allow admin to tells that the sieve server use utf8 instead
    "SOGoIMAPAclStyle": None, #There some change between rfc2086 and rfc4314 for acl https://datatracker.ietf.org/doc/html/rfc4314#appendix-A
                                               #TODO still relevant? The new rfc is from 2005 so dovecot/cyrus must be updated since.
    "SOGoIMAPAclConformsToIMAPExt": None, #Even not used by SOGo 5 anymore, read the capabilities and check for any starting with acl2
                                         #TODO not sure what this is, almost no sign of that -> https://www.rfc-editor.org/rfc/rfc4314.html#appendix-C
                                         #not listed too, https://www.iana.org/assignments/imap-capabilities/imap-capabilities.xhtml
                                         #the only thing that does https://github.com/Alinto/sogo/blob/b69ef6d7a58da32954fed6636aed18524137b017/SoObjects/Mailer/SOGoMailFolder.m#L1510
    
    "SOGoMailSpoolPath": None,            #Path where temp files are stored for draft messages beofre being sent to the imap server.
    "NGMimeBuildMimeTempDirectory": None, #Same but for mime message. SOGo6's mean to store temp message should be way different.
                                          #It seems to be use to avoid storing all the data in the running code as it can be heavy
                                          #So, stored in a file, and when needing to be sent, read the file. #TODO not bad, an email can be heavy.
    "NGImap4DisableIMAP4Pooling": None, #SO much useless work to save a connection request...
                                                                #Change default value in SOGO 6, NO meaning no pool instead of YES = disable pool
                                                                #TODO ask exploit about that. I was so confused when JMAP dev tell me imap needs
                                                                #lasting connection, happends that sogo cuts it after 5 min by default.
                                                                #After  minutes, sogo does a simple logout command to the imap server
    "NGImap4ConnectionGroupIdPrefix": None, #TODO Apprently there are goups defined in imap server (statring with $ or @)
                                          #This is a unix thing, see https://en.wikipedia.org/wiki/Group_identifier

    #Webmail config
    "SOGoExternalAvatarsEnabled": "SOGO_D_ALLOW_EXT_AVATAR", #Allow user to load external avatar like gravatar
    "SOGoRefreshViewIntervals": "SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED", #Set what refresh interval (for mail) is available to users
 
    #Sieve
    "SOGoSieveScriptsEnabled": "SOGO_D_MAIL_FILTERING_ENABLED", #Allow user to set sieve filters
    "SOGoSieveScriptHeaderTemplateFile": "SOGO_D_SIEVE_HEADER", #Set a siever filter that will at the head of each user, was a path to a sieve file now is directly a ddb ready value
    "SOGoSieveScriptFooterTemplateFile": "SOGO_D_SIEVE_FOOTER", #Set a siever filter that will at the foot of each user, was a path to a sieve file now is directly a ddb ready value
    "SOGoVacationEnabled": "SOGO_D_VACATION_ENABLED", #Allow user to set a sieve autoreply. (default value change)
    "SOGoVacationPeriodEnabled": None, #Was used in case the sieve server hadn't the capability "date". They all have it by now.
    "SOGoVacationDefaultSubject": None , #default vacancy (autoreply) subject if not set by the user. it was "Auto: <original_subject>".
                                         #TODO change this to a prefix, e.g. if you want your campany name to be at first
    "SOGoVacationHeaderTemplateFile": "", #TODO was a path to the hmtl template vor vacancy message. Is still useful as the user will only add a text not a full html message.
    "SOGoVacationFooterTemplateFile": "", #See above
    "SOGoVacationAllowZeroDays": "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS", #Allow user to set 0 for vacation response delay, meaning the vacation will be send to every message without delay.
                                    #It was a community PR but the rfc does not agree -> https://datatracker.ietf.org/doc/html/rfc5230.html#section-4.1, dovecot seems to allow that
                                    #https://doc.dovecot.org/2.3/settings/pigeonhole-ext/vacation/#pigeonhole_setting-sieve_vacation_min_period
    "SOGoForwardEnabled": "SOGO_D_FORWARD_ENABLED", #ALlow user to set a forward rule (default value change)
    "SOGoForwardConstraints": None, #Set constraint on which domain you can or not set a forward rule
                                                           #TODO refactor the constrains system as it was not great on sogo (onlt whitelist, no blalcklist...)
                                                           #0 -> "No constraints"
                                                           #1 -> "Only internals domains"
                                                           #2 -> "Only extenral domain"
                                                           #3 -> "Internals domains + SOGoForwardConstraintsDomains"
    "SOGoForwardConstraintsDomains": None, #See SOGoForwardConstraints
    "SOGoNotificationEnabled": "SOGO_D_NOTIFY_ENABLED", #Allow user to set notify sieve rule (default value change)
}

#See UserSource in DomainSettings.py
#As it was often written "ldap fields or SQL columns", a shorcut was made "sqldap field"
user_source_256 = {
    "type": "US_TYPE", #'sql" or 'ldap'
    "id":   "US_UID", #name used by sogo to identifies this user source among the others, must be unique

    #Common
    "MailFieldNames": "US_MAIL", #Array of sqldap field that tell the user's mail. Default to ('mail'). Should be ('mail", 'alias')
    "SearchFieldNames": "US_SEARCH", #Array of sqldap field that will be query when doing an autocompletion/search of user.
    "IMAPHostFieldName ": None, #sqldap field with the IMAP server's hostname for the user
                                #Too much config available. A User Source is in a domain where an IMAP server ca be config +
                                #SOGo6 is agnostic about the mail server (Imap, Jmap?) + do an imap proxy for that.
                                ###ALAS, somes uses it...........
                                #OK WE KEEP THAT IN SOGO 6 !!!!!!!!
    "IMAPLoginFieldName ": "US_MAIL_SERVER_LOGIN", #sqldap field where to fetch the imap login for a user (default to UIDFieldName for ldap or c_uid for sql)
    "SieveHostFieldName ": "US_MAIL_FILTERING_LOGIN", #See IMAPHostFieldName.

    "userPasswordAlgorithm": "US_PWD_ALGO", #Encryption algorithm for users' password (#TODO keep all crypt supported by sogo? )
                                            #https://bugs.sogo.nu/view.php?id=5837
                                            #https://bugs.sogo.nu/view.php?id=4869
    "keyPath":               "US_PWD_ALGO_SIM_KEY", #SYmetric key when the algo needs one.
                                                    #On sogo 5 this is the path of a file, in sogo 6 we can set i differently, see US_PWD_ALGO_SIM_KEY 
    "canAuthenticate":       "US_CAN_AUTH", #This user source is used for authentication (ohterwise used for Address Book and autocompletion)
    "isAddressBook":         "US_IS_ADDRESSBOOK", #True if this user source is an address book and will be shown in shared address book.
    "displayName":           "US_DISPLAY_NAME", #human name of this US
    "listRequiresDot":       "US_AUTO_SEARCH", #If set to yes, listing this address book will be automatic. If no, the user willl need to type some chars
                                               #or a dot to see all. Careful the bool value is the opposite
    "globalAddressBookFirstEntriesCount": None, #Number of max users return when listRequiresDot is False. No need to migrate, is the server the decide
                                                #how much to return with pagination?
    "disableSubgroups": None, #It was add for a problem with SOGo5 that was looping when looking at a user with the same name as a group.
                              #No need to migrate it as the problem won't be migrated ;)
    "ModulesConstraints": None, #Used to limit access to Mail, Calendar, ActiveSYnc to users dependings on a colomn
                                #Exemple: only user with c_test = mailer can access Mail
                                #TODO, move to domain settings SOGO_D_MODULE_ACCESS
        
    "mapping": "US_MAPPING", #TODO map sqldap field to vcard field https://www.sogo.nu/files/docs/SOGoInstallationGuide.html#_ldap_attributes_mapping

    #Common resource
    "KindFieldName":      "US_KIND", #sqldap field to see the kind of 'user', if the value is among "group", "location" or "thing"
                                      #this is a resource and not a user. For ldap, SOGo also detect a resource if it has objectClass: CalendarResource
                                      #TODO warning, there is an extra parameters to set for this one US_HAS_RESOURCE
    "MultipleBookingsFieldName": "US_RESOURCE_MULTIBOOKING", #sqldap field to set how much a resource can be silmutaneously booked.
                                                             #0 -> no limit
                                                             #-1 -> no limit but the resource will be busy the first time it is booked
                                                             #5 -> can be booked up to 5 times.



    #Ldap #TODO
    #CN = Common Name
    #OU = Organizational Unit
    #DC = Domain Component
    "hostname":   "US_LDAP_HOSTNAME", #ldap hostname, drop the ldap url support defined in https://datatracker.ietf.org/doc/html/rfc4516
    "port":       None, #already deprecated in SOGo 5, use in hostname instead
    "encryption": None,  #already deprecated in SOGo 5, use in hostname with ldaps instead of ldap
    "passwordPolicy": "US_US_LDAP_PWD_POLICY", #doesn't define the password policy but tell SOGO that the ldap server has the extension password policy
                                         #https://www.ietf.org/archive/id/draft-behera-ldap-password-policy-11.html
                                         #https://www.rfc-editor.org/rfc/rfc3062.html
    "updateSambaNTLMPasswords": "US_LDAP_PWD_UPDATE_SAMBA", #For samba extension (https://www.samba.org/) update the correct field for the password

    "CNFieldName": "US_LDAP_CN", #Value being the common name default to 'cn'
    "IDFieldName": "US_LDAP_ID", #Uded to make the baseDN request: meaning query where 'IDFieldName' = login + baseDN setting
                              #Login in SOGo5 can be a login completely different of the mail. default to cn
                              #TODO not sure about the diff between IDFieldName and UIDFieldName
    "UIDFieldName": "US_LDAP_UID", #Unique ID of a user.
    "baseDN":       "US_LDAP_BASE_DN", # The base DN use to fetch the users. We can add %d that will be replace by the current user mail domain.
    "filter":       "US_LDAP_FILTER", #Additionnal filter for the ldap query. Careful, SOGo5 has a peculiar syntax for the value.
    "scope":        "US_LDAP_SCOPE", #Scope for the ldap query

    "bindDN":             "US_LDAP_BIND_DN", #The bind DN used to authnetify against the ldap server
    "bindPassword":       "US_LDAP_BIND_PWD", #The password for the bindDN
    "bindAsCurrentUser":  "US_LDAP_BIND_AS_USER", #After the fist auth, use the user's DN for the bind DN
    "bindFields":         "US_LDAP_BIND_FIELD", #Additionnal field to use when doing a bind
    "lookupFields":       "US_LDAP_ATTR_FIELD", #Fields return for ldap query, default to '*'. IS used to return operationl field like 'memberOf'
    "GroupObjectClasses": "US_LDAP_GROUP_CLASS", #Value for 'objectclass' that tell this is a group of user

    "SOGoLDAPQueryTimeout": "US_LDAP_QUERY_TIMEOUT", #a paramater for ldap library's query method
    "SOGoLDAPGroupExpansionEnabled": None, #Parameter to expand ldap group. To None because why we want t odisable that?

    "modifiers": None, #DO NOT MIGRATE List of user allowed to modify user from the usersource in the webmail
                      #I think it's best that they have their own tools to modify the user source (+ it's broken on sogo 5)
    "objectClasses": None, #List of value for field 'objectClass' added when modifiers is set and the user modify the source.

    "abOU": None, #DO NOT MIGRATE User can have their addressbook in the ldap server instead of the database.

    #Was ldap but moved to be common to both sql and ldap
    "SOGoLDAPContactInfoAttribute": "US_EXTRA_CONTACT_INFO", #sqldap field with a string to show when doing autocompletion (it's cn <extra> mail)
    "SOGoLDAPQueryLimit": "US_AUTO_QUERY_LIMIT", #The maximum result a query return when doing autocompletion

    #SQL
    "viewURL": "SQL_USER_URL", #database url for the user sources
    "userPasswordPolicy": "US_PWD_POLICY", #PAssword polic yused by sogo when changing password or checkin the weakness at login.
    "prependPasswordScheme": "SQL_PREPEND_PWD_SCHEME", #the password stored in teh database will have the scheme before the encrypte value like {scheme}encryptedPass

    "authenticationFilter": "SQL_USER_FILTER", #additionnal where clause when querying the users

    "LoginFieldName": None, #TODO default to c_uid, we could defined here mutliple column to check the user login
                           #Like 'WHERE (field1 = login OR field2 = login...). But uneccessary as in sql we force the table strucuture as opposite of ldap who already have its own structure

    "DomainFieldName": "SQL_DOMAIN_FIELD", #sql column where to fing the domain of the user

}

users_526 = {

    #Common
    "SOGoLanguage": "SOGO_U_LANGUAGE", #USer language
    "SOGoTimeZone": "SOGO_U_TIMEZONE", #Timezone for the user
    "SOGoTimeFormat": "SOGO_U_TIME_FORMAT", #format of the time. Beware, you have to convert objective c format to react format
    "SOGoDayStartTime": "SOGO_U_WORKDAY_START_TIME", #Tell at which hour the workday start, use by other functionalities
    "SOGoDayEndTime": "SOGO_U_WORKDAY_END_TIME",     #Same but for the end
    "SOGoBusyOffHours": "SOGO_U_BUSY_OFF_HOURS", #Automaticaly be busy outside of working hour defined by SOGoDayStartTime and SOGoDayEndTime

    #Passwords
    #TODO Should not migrate that sensitive data about a user
    "SOGoPasswordRecoveryMode": None, #Method (singular) set to recover password. Was SecretQuetion or SecondaryEmail in SOGo5
                                                              #SHould be a tuple of all methods set
    "SOGoPasswordRecoveryQuestion":       None,        #In SOGo 5 the question is written by the user as well as the answer (not bad)
    "SOGoPasswordRecoveryQuestionAnswer": None, #Beware, answer and question should'nt be in plain text in database
    "SOGoPasswordRecoverySecondaryEmail": None, #Only one mail for SOGo5, several for SOGo 6?

    #Mail Folders' name, user can change which folder is what from the webmail
    #TODO it does not change any imap property, it only change the name folder when you're doing action from webui like trash or junk
    #Inbox is not affected
    "SOGoDraftsFolderName": "SOGO_U_DRAFT_FOLDER_NAME", #Name of the draft folder, default to 'Drafts' (translated).
    "SOGoSentFolderName":   "SOGO_U_SENT_FOLDER_NAME", #Name of the sent folder, default to 'Sent' (translated).
    "SOGoTrashFolderName":  "SOGO_U_TRASH_FOLDER_NAME", #Name of the trash folder, default to 'Trash' (translated).
    "SOGoJunkFolderName":   "SOGO_U_JUNK_FOLDER_NAME", #Name of the junk folder, default to 'Junk' (translated).

    #Accounts and mail
    "SOGoMailShowSubscribedFoldersOnly": None, #TODO Only show subscribed mail folders... why?
    "SOGoMailAuxiliaryUserAccountsEnabled": "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT", #Allow user to add external account to their webmail
    "SOGoMailMessageForwarding": "SOGO_U_MAIL_FORWARDING_FORMAT", #Tell if the forwaded mail is in the body or in a attachment
    "SOGoMailDisplayFullEmail": None, #Instead of just showing the name of the sender, also display the full mail address
                                      #TODO Remove from SOGo 6 because it's on a tooltip instead.
    "SOGoMailHideInlineAttachments": "SOGO_U_HIDE_INLINE_ATTACHMENT", #Do not hsow inline image as attachment in the webmail (useful with small pics for social networks)
    "SOGoMailCustomFullName": None, #Was not used in SOGo5 anymore, only in previous version.
    "SOGoMailCustomEmail": None, #Idem
    "SOGoMailReplyTo": None, #Idem
    "SOGoMailReplyPlacement": "SOGO_U_REPLY_POSITION", #When replying to a mail, where to put the original message: above or below the user answer?
    "SOGoMailSignaturePlacement": "SOGO_U_SIGNATURE_POSITION", #When replying, forwarding a mail where to put the signature. Below the quoted message or above it
    "SOGoMailUseSignatureOnNew": None, #TODO Instead of three settings, convert them in a list SOGO_U_USE_SIGNATURE
    "SOGoMailUseSignatureOnReply": None, #idem
    "SOGoMailUseSignatureOnForward": None, #Idem
    "SOGoMailComposeMessageType": "SOGO_U_COMPOSE_MAIL_TYPE_DEFAULT", #TODO Should be a switch on the mail editor instead of a settings BUT is the default value
    "SOGoMailComposeWindow": "SOGO_U_COMPOSE_MAIL_WINDOW", #When writting a new mail, is in an inline html or a pop up?

    #Web page
    "SOGoLoginModule": "SOGO_U_FIRST_MODULE", #Tell what module (mail, calendar, contacts, last one used) to show first after connection
                                              #TODO name changds (full lowercase)
    "SOGoGravatarEnabled": "SOGO_U_GRAVATAR_ENABLED", #Allow to load gravatar pic if SOGO_D_ALLOW_EXT_AVATAR is enabled
    "SOGoRefreshViewCheck": "SOGO_U_REFRESH_MAIL_VIEW", #Tell if the mail view lust be refresh manually or for some interval.
    
    #Calendar view
    "SOGoDefaultCalendar": "SOGO_U_CALENDAR_DEFAULT", #Name to the default calendar when creating event
    "SOGoFirstDayOfWeek": "SOGO_U_CALENDAR_VIEW_FIRST_DAY", #First day of the week for calendar week and months views
    "SOGoFirstWeekOfYear": "SOGO_U_CALENDAR_WEEK_NUMBER_FORMAT", #Tell how week number is evaluated, three values:
                                                                #'January1' -> not available in python
                                                                #'First4DayWeek' -> '%V' in datetime format
                                                                #'FirstFullWeek' -> either %U (first sunday) or %W (first monday)
    "SOGoCalendarCategories": "SOGO_U_CALENDAR_CATEGORIES", #Name of the calendar categories, in an array 
    "SOGoCalendarCategoriesColors": None,                     #Colors of the calendar categories, in an array with same index
                                                            #TODO rework that for SOGo6 to not have 2 arrays, array of tuple (name, color, is_default)
                                                            #is_default means that the categorie was here by default, and can be translated.
                                                            #is_default = False means this is custom categorie from the user can can't be translated
    "SOGoCalendarEventsDefaultClassification": "SOGO_U_EVENT_DEFAULT_CLASS", #Which event class is set when creating new event (public, confidential, private)
    "SOGoCalendarTasksDefaultClassification":  "SOGO_U_TASK_DEFAULT_CLASS", #Which task class is set when creating new task (public, confidential, private)
    "SOGoCalendarDefaultReminder": "SOGO_U_EVENT_DEFAULT_REMINDER", #Default reminder used for new events she enabling it

    #Contacts
    "SOGoMailAddOutgoingAddresses": "SOGO_U_COLLECT_UNKNWON_ADDRESSES", #Boolean, set to yes ot add unknwon address (= not in any addressbook folders, including the global one)
                                                                       #Add it to the next address book
    "SOGoSelectedAddressBook": "SOGO_U_COLLECT_UNKNWON_ADDRESSEBOOK_NAME", #Name of the address book that collects all unknwonw address, default to 'Collected' (translated)
    "SOGoContactsCategories": "SOGO_U_CONTACT_CATEGORIES", #List of contacts category #TODO format change in SOGo 6


    #Sieve
    "SOGoSieveFilters": "SOGO_D_SIEVE_FIRST_FILTER", #First sieve filtre set for new users, can be changed afterwards.
}
