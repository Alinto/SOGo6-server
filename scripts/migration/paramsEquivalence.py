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

    # Authentication made by a proxy and sogo trust it
    "SOGoTrustProxyAuthentication": "#TODO", #see backArchi info in Authentication chapter
    "SOGoEncryptionKey":            "#TODO",

    # Cache system, change from memcached to redis
    "SOGoCacheCleanupInterval": "SOGO_P_REDIS_TTL", # ENV, but do we set it for all params????
    "SOGoMemcachedHost":        None, # Redis is used now, see SOGO_P_REDIS_URL.


    # Calendar Settings
    "SOGoCalendarEnableJitsiLink": "SOGO_D_JITSI_LINK_ENABLED", #Move to domain, careful default value was False and is now True
                                                                #Also see SOGoCalendarJitsiBaseUrl in domain_526

    # DAV settings, now is domain
    "SOGoAddressBookDAVAccessEnabled": "SOGO_D_DAV_CONTACT_ENABLED",
    "SOGoCalendarDAVAccessEnabled":    "SOGO_D_DAV_CALENDAR_ENABLED",

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

    #Mailing - Those parameters are also set byt the SMTP server, but it tells sogo how to act before actually requetsing the smtp server
    "SOGoMaximumMessageSubmissionCount":  "SOGO_D_MAIL_MAX_SUBMISSION", #Maximum mail an user san send during SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL
    "SOGoMaximumRecipientCount":          "SOGO_D_MAIL_MAX_RECIPIENT", #Maximum recepient allowed by SOGo
    "SOGoMaximumSubmissionInterval":      "SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL", #Interval for SOGO_D_MAIL_MAX_SUBMISSION
    "SOGoMessageSubmissionBlockInterval": "SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl", #Number of seoncds when a user is forbid to send mail after SOGO_D_MAIL_MAX_SUBMISSION

    #Passwords
    "SOGoPasswordRecoveryEnabled": "SOGO_D_PWD_RECOVERY", #Allow user to set a method to recover passwords
    "SOGoPasswordRecoveryDomains": None, #Allow domains that enable password recovery if SOGoPasswordRecoveryEnabled not set
                                         #Moving those to domains, so only SOGO_D_PWD_RECOVERY is used, there were also SOGoPasswordRecoveryFrom already in domain

    "SOGoJWTSecret": None, #Token used encrypt/decrypt word used in secondary email passsword recovery. No need to migrate

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


}

domain_526 = {

    # Admin
    "SOGoSuperUsernames":         None, #TODO, there is rework of admin users and what they can do.
    "SOGoPasswordChangeEnabled": "SOGO_D_PWD_CHANGE_ENABLED", #Allow users to change the password (for ldap it means the ldap admin account is allow to do that too)

    # Calendar Settings
    "SOGoAppointmentSendEMailNotifications": None, #TODO Is it useful? To forbid user to send update to others when modifying event
                                                   #It should be a choice when the user modify the event.
                                                   #I see a case where sogo is only used for calendar sharing and does not have a smtp server...
    "SOGoCalendarDefaultRoles":          None, #TODO Determines the 'default' acl of a user when opening the share view. Feels useless?
    "SOGoCalendarJitsiBaseUrl":          "SOGO_D_JITSI_BASE_URL", #See SOGoCalendarEnableJitsiLink in system_526
    "SOGoCalendarJitsiRoomPrefix":       None, #Merge with SOGO_D_JITSI_BASE_URL = SOGoCalendarJitsiBaseUrl + SOGoCalendarJitsiRoomPrefix
    "SOGoHideSystemEMail":               None, #Hide the true value for calendar-user-address-set DAV param. No need and no info on that on internet. 
    "SOGoiPhoneForceAllDayTransparency": None, #Made in 2010 to force allDay event coming from iphone to be transparent for freebusy, irrelevant today.
    "SOGoNotifyOnPersonalModifications": None, #Useless as user can ovveride it in calendar property
    "SOGoNotifyOnExternalModifications": None, #Useless as user can ovveride it in calendar property

    # Contact setting
    "SOGoContactsDefaultRoles": None, #TODO Determines the 'default' acl of a user when opening the share view. Feel useless?

    # Folder settings
    "SOGoACLsSendEMailNotifications":    None, #TODO It should be mandatory to tell user when they now have rights on anoter folder.
    "SOGoDisableExport":                 "SOGO_D_FOLDER_DISABLE_EXPORT", #Disable sharing of folders (remove the uppercase for value)
    "SOGoDisableSharing":                "SOGO_D_FOLDER_DISABLE_SHARING", #Disable sharing of folders (remove the uppercase for value)
    "SOGoDisableSharingAnyAuthUser":     "SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH", #Disable sharing for any authenticated user (remove the uppercase for value)
    "SOGoEnablePublicAccess":            "SOGO_D_DAV_PUBLIC_ACCESS_ENABLE", #Enable public acces to dav link
    "SOGoFoldersSendEMailNotifications": "SOGO_U_FOLDER_CREATION_NOTIF", #Was domain but better at user's, change the default from False to True
    "SOGoSearchMinimumWordLength":       "SOGO_D_AUTOCOMPLETION_MIN_LEN", #Minimum length of chars before searching for autocompletion

    #Imap Identities
    "SOGoCreateIdentitiesDisabled": "SOGO_D_IDENTITIES_ENABLED", #Allow user to create identities (from, reply-to, name, signature)
                                                                 #Behavior change in SOGo 6 #TODO

    # LDAP
    "SOGoLDAPContactInfoAttribute": "", #TODO Should be in UserSource, LDAP attribute to show for autocompletion (default Name <mail>)

    # Mail Editor
    "SOGoForceRawHtmlSignature": None, #SHould be set t oYES in our case (value by default in SOGo5) -> https://bugs.sogo.nu/view.php?id=5920
                                       #Needs work on CKeditor in SOGo6 to fully undesrtand it. Should be domain bu process.

    # Mailing
    "SOGoMailDomain":          None, #Not veen use in SOGo 5...  
    "SOGoMailDisableXForward": None, #SOGo 5 automatically added an header X-Forward with the nginx custom sogo
                                     #x-webobjects-remote-host ip, not necessary? #TODO ask exploit

    # Password
    "SOGoPasswordRecoveryFrom": "", #TODO Set the from used for send if the recovery password with secondary email method.
                                    #Useful? Is this not defines by the smtp server? The mail use for tasks like postmaster....

    #User source
    "SOGoUserSources": None #TODO so much rework for that... see here dict user_source_256
}

#See UserSource in DomainSettings.py
#As it was often written "ldap fields or SQL columns", a shorcut was made "sqldap field"
user_source_256 = {
    "type": "US_TYPE", #'sql" or 'ldap'
    "id":   "US_ID", #name used by sogo to identifies this user source among the others, must be unique

    #Common
    "MailFieldNames": "US_MAIL", #Array of sqldap field that tell the user's mail. Default to ('mail'). Should be ('mail", 'alias')
    "SearchFieldNames": "US_SEARCH", #Array of sqldap field that will be query when doing an autocompletion/search of user.
    "IMAPHostFieldName ": None, #sqldap field with the IMAP server's hostname for the user
                                #Too much config available. A User Source is in a domain where an IMAP server ca be config +
                                #SOGo6 is agnostic about the mail server (Imap, Jmap?) + do an imap proxy for that.
    "IMAPLoginFieldName ": "US_IMAP_LOGIN", #sqldap field where to fetch the imap login for a user (default to UIDFieldName for ldap or c_uid for sql)
    "SieveHostFieldName ": None, #See IMAPHostFieldName.

    "userPasswordAlgorithm": "US_PWD_ALGO", #Encryption algorithm for users' password
    "canAuthenticate":       "US_CAN_AUTH", #This user source is used for authentication (ohterwise used for Address Book and autocompletion)
    "isAddressBook":         "US_IS_ADDRESSBOOK", #True if this user source is an address book and will hos in sheard address book.
    "displayName":           "US_DISPLAY_NAME", #human name of this US
    "listRequiresDot":       "US_AUTO_SEARCH", #If set to yes, listing this address book will be automatic. If no, the user willl need to type some chars
                                               #or a dot to see all. Careful the bool value is the opposite
    "globalAddressBookFirstEntriesCount": None, #Number of max users return when listRequiresDot is False. No need to migrate, is the server the decide
                                                #how much to return with pagination?
    "disableSubgroups": None, #It was add for a problem with SOGo5 that was looping when looking at a user with the same name as a group.
                              #No need to migrate it as the problem won't be migrated ;)
    "ModulesConstraints ": None, #Used to limit access to Mail, Calendar, ActiveSYnc to users dependings on a colomn
                                 #Exemple: only user with c_test = mailer can access Mail
                                 #TODO, migrate it? It already exist the same for domains.
    
                    
    


    #Common resource
    "KindFieldName ":      "US_KIND", #sqldap field to see the king of 'user', if the value is among "group", "location" or "thing"
                                      #this is a resource and not a user. For ldap, SOGo also detect a resource if it has objectClass: CalendarResource
    "MultipleBookingsFieldName": "US_RESOURCE_MULTIBOOKING", #sqldap field to set how much a resource can be silmutaneously booked.
                                                             #0 -> no limit
                                                             #-1 -> no limit but the resource will be busy the first time it is booked
                                                             #5 -> can be booked up to 5 times.



    #Ldap #TODO
    #CN = Common Name
    #OU = Organizational Unit
    #DC = Domain Component
    "hostname":   "LDAP_HOSTNAME", #ldap hostname, drop the ldap url support defined in https://datatracker.ietf.org/doc/html/rfc4516
    "port":       None, #already deprecated in SOGo 5, use in hostname instead
    "encryption": None,  #already deprecated in SOGo 5, use in hostname with ldaps instead of ldap
    "passwordPolicy": "LDAP_PWD_POLICY", #doesn't define the password policy but tell SOGO that the ldap server has the extension password policy
                                         #https://www.ietf.org/archive/id/draft-behera-ldap-password-policy-11.html
    "updateSambaNTLMPasswords": "LDAP_SAMBA_PWD", #For samba extension (https://www.samba.org/) update the correct field for the password

    "CNFieldName": "LDAP_CN", #Value being the common name default to 'cn'
    "IDFieldName": "LDAP_ID", #Uded to make the baseDN request: meaning query where 'IDFieldName' = login + baseDN setting
                              #Login in SOGo5 can be a login completely different of the mail. default to cn
                              #TODO not sure about the diff between IDFieldName and UIDFieldName
    "UIDFieldName": "LDAP_UID", #Unique ID of a user.
    "baseDN":       "LDAP_BASE_DN", # The base DN use to fetch the users. We can add %d taht will be replace by the current user mail domain.
    "filter":       "LDAP_FILTER", #Additionnal filter for the ldap query. Careful, SOGo5 has a peculiar syntax for the value.
    "scope":        "LDAP_SCOPE", #Scope for the ldap query

    "bindDN":            "LDAP_BIND_DN", #The bind DN used to authnetify against the ldap server
    "bindPassword":      "LDAP_BIND_PWD", #The password for the bindDN
    "bindAsCurrentUser": "LDAP_BIND_AS_USER", #After the fist auth, use the user's DN for the bind DN
    "bindFields":        "LDAP_BIND_FIELD", #Additionnal field to use when doing a bind
    "lookupFields":      "LDAP_LOOKUP_FIELD", #Fields return for ldap query, default to '*'. IS used to return operationl field like 'memberOf'

    #SQL

}

users_526 = {

    #Common
    "SOGoLanguage": "SOGO_U_LANGUAGE", #USer language
    "SOGoTimeZone": "SOGO_U_TIMEZONE", #Timezone for the user

    #Passwords
    #TODO Should not migrate that sensitive data about a user
    "SOGoPasswordRecoveryMode": None, #Method (singular) set to recover password. Was SecretQuetion or SecondaryEmail in SOGo5
                                                              #SHould be a tuple of all methods set
    "SOGoPasswordRecoveryQuestion":       None,        #In SOGo 5 the question is written by the user as well as the answer (not bad)
    "SOGoPasswordRecoveryQuestionAnswer": None, #Beware, answer and question should'nt be in plain text in database
    "SOGoPasswordRecoverySecondaryEmail": None, #Only one mail for SOGo5, several for SOGo 6?

}
