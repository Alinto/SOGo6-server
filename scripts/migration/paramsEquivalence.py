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
    "SOGoCacheCleanupInterval": "SOGO_S_REDIS_TTL", # ENV, but do we set it for all params????
    "SOGoMemcachedHost":        None, # Redis is used now, see SOGO_S_REDIS_URL.


    # Calendar Settings
    "SOGoCalendarEnableJitsiLink": "SOGO_D_JITSI_LINK_ENABLED", #Move to domain, careful default value was False and is now True
                                                                #Also see SOGoCalendarJitsiBaseUrl in domain_526

    # DAV settings, now is domain
    "SOGoAddressBookDAVAccessEnabled": "SOGO_D_DAV_CONTACT_ENABLED",
    "SOGoCalendarDAVAccessEnabled":    "SOGO_D_DAV_CALENDAR_ENABLED",

    # Language
    "SOGoSupportedLanguages": None, #TODO, it's to limit the languages available for users (SOGoLanguage). Useless and not inclusive.

    # Logging
    "WOLogFile": None, # The logfile path is fixed in SOGo 6

    # Process/Memory settings, now handle by gunicorn/docker/kubernetes
    "SxVMemLimit":    None, # Managed by kubernetes or container
    "WOPidFile":      None, # Non-revelant for SOGo 6, managed by gunicorn/faslk
    "WOWorkersCount": None, # Non-revelant for SOGo 6, manages by Gunicorn setting 'workers'

    # Webserver settings, now handle by flask/gunicorn
    "SOGoMaximumMessageSizeLimit": None, # see WOMaxUploadSize
    "WOListenQueueSize":           None, # Value shouldn't be migrated because new techno. Gunicorn setting 'backlog'
    "WOMaxUploadSize":             None, # See MAX_CONTENT_LENGTH, MAX_FORM_MEMORY_SIZE, MAX_FORM_PARTS
                                         # for flask https://flask.palletsprojects.com/en/stable/config/
                                         # and for gunicorn https://docs.gunicorn.org/en/stable/settings.html#security
    "WOPort":                      None, # Do not migrate. For flask options --port. For Gunicorn, see setting 'bind'
    "WOWatchDogRequestTimeout":    None, # Do not migrate. Set by gunicorn settings 'timeout'


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
    "SOGoContactsDefaultRoles": None, #TODO Determines the 'default' acl of a user when opening the share view. Feels useless?


    # Folder settings
    "SOGoACLsSendEMailNotifications":    None, #TODO It should be mandatory to tell user when they now have rights on anoter folder.
    "SOGoDisableExport":                 "SOGO_D_FOLDER_DISABLE_EXPORT", #Disable sharing of folders (remove the uppercase for value)
    "SOGoDisableSharing":                "SOGO_D_FOLDER_DISABLE_SHARING", #Disable sharing of folders (remove the uppercase for value)
    "SOGoDisableSharingAnyAuthUser":     "SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH", #Disable sharing for any authenticated user (remove the uppercase for value)
    "SOGoEnablePublicAccess":            "SOGO_D_DAV_PUBLIC_ACCESS_ENABLE", #Enable public acces to dav link
    "SOGoFoldersSendEMailNotifications": "SOGO_U_FOLDER_CREATION_NOTIF", #Was domain but better at user's, change the default from False to True
    "SOGoSearchMinimumWordLength":       "SOGO_D_AUTOCOMPLETION_MIN_LEN", #Minimum length of chars before searching for autocompletion

    # LDAP
    "SOGoLDAPContactInfoAttribute": "", #TODO Should be in UserSource, LDAP attribute to show for autocompletion (default Name <mail>)

    # Mailing
    "SOGoMailDomain":          None, #Not veen use in SOGo 5...  
    "SOGoMailDisableXForward": None, #SOGo 5 automatically added an header X-Forward with the nginx custom sogo
                                     #x-webobjects-remote-host ip, not necessary? #TODO ask exploit
}

users_526 = {

    #Common
    "SOGoLanguage": "SOGO_U_LANGUAGE", #USer language
    "SOGoTimeZone": "SOGO_U_TIMEZONE", #Timezone for the user

    
}
