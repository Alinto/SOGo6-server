from marshmallow import Schema, fields

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class AdminConfigDynamicFormData(Schema):
    """
    Data schema of the result for /dynamic-form
    """
    domain = fields.List(fields.Dict())
    system = fields.List(fields.Dict())


class AdminConfigDynamicFormSchemaRet(ApiBaseResponse):
    """
    Schema of the result for GET /dynamic-form 
    """
    data = fields.Nested(AdminConfigDynamicFormData)



class AdminConfigSystemGetRetSchema(ApiBaseResponse):
    """
    Schema of the result GET /system
    """
    data = fields.Dict()

    @classmethod
    def example(cls) -> dict:
        """
        Example of result for GET /system

        :return: example
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "SYSTEM_SETTINGS": {
                    "SOGO_S_DOMAINLESS_LOGIN": False,
                    "SOGO_S_DO_DOMAIN": True,
                    "SOGO_S_MAILSPOOL_PATH": "/var/spool/sogo",
                    "SOGO_S_REJECT_UNKNOWN_DOMAIN": False,
                    "SOGO_S_SENDMAIL": "/usr/lib/sendmail"
                }
            }
        }

class AdminConfigSystemPatchSchema(Schema):
    """
    Schema of the body expected for patching system settings

    Expected JSON Merge Patch data
    """
    settings  = fields.Dict(required=True, keys=fields.String(), values=fields.Raw())

    @classmethod
    def example(cls) -> dict:
        """
        Example of data for the post request

        :return: Example data
        :rtype: dict
        """
        return {
            "settings": {
                "SYSTEM_SETTINGS": {
                    "SOGO_S_DO_DOMAIN": True,
                    "SOGO_S_KNOWN_DOMAIN": ["sogo.nu"],
                    "SOGO_S_REJECT_UNKNOWN_DOMAIN": False,
                    "SOGO_S_DOMAINLESS_LOGIN": False,
                    "SOGO_S_SENDMAIL": "/usr/lib/sendmail",
                    "SOGO_S_MAILSPOOL_PATH": "/var/spool/sogo"
                }
            }
        }


class AdminConfigDefaultDomainGetSchema(ApiBaseResponse):
    """
    Sceham for GET domain

    :param ApiBaseResponse: _description_
    :type ApiBaseResponse: _type_
    """

    data = fields.Dict()

    @classmethod
    def example(cls) -> dict:
        """
        Example of data for the post request

        :return: Example data
        :rtype: dictAdminConfigDomainPostSchema
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "AUTH_SETTINGS": {
                    "SOGO_D_AUTH_TYPE": "plain",
                    "SOGO_D_PWD_CHANGE_ENABLED": True,
                    "SOGO_D_PWD_RECOVERY": True,
                    "SOGO_D_PWD_RECOVERY_METHOD": [
                        "secretQuestion",
                        "secondaryEmail"
                    ],
                    "SOGO_D_PWD_RECOVERY_FORCE": False,
                    "SOGO_D_PWD_RECOVERY_DELAY": 86400,
                    "SOGO_D_LOGIN_MFA": True,
                    "SOGO_D_LOGIN_MFA_METHOD": [
                        "totp"
                    ],
                    "SOGO_D_LOGIN_MFA_FORCE": False
                },
                "USER_SOURCE": {
                    "us_french": {
                        "US_UID": "ldap_ex",
                        "US_NAME": "us_french",
                        "US_TYPE": "ldap",
                        "US_LDAP_HOSTNAME": "ldap://openldap:390",
                        "US_LDAP_BIND_DN": "cn=admin,dc=example,dc=org",
                        "US_LDAP_BIND_DN_PWD": "password",
                        "US_LDAP_BASE_DN": "ou=users,dc=example,dc=org",
                        "US_LDAP_UID": "uid",
                        "US_LDAP_CN": "cn",
                        "US_LDAP_ID": "uid",
                        "US_LDAP_SCOPE": "SUB",
                        "US_LDAP_QUERY_TIMEOUT": 0,
                        "US_LDAP_BIND_AS_USER": False,
                        "US_LDAP_ATTR_FIELD": [
                            "*"
                        ],
                        "US_LDAP_GROUP_CLASS": [
                            "group",
                            "groupOfNames",
                            "groupOfUniqueNames",
                            "posixGroup"
                        ],
                        "US_CAN_AUTH": True,
                        "US_PWD_POLICY": False,
                        "US_PWD_LEN_MIN": 3,
                        "US_PWD_LEN_MAX": 0,
                        "US_MAIL": [
                            "mail"
                        ],
                        "US_KIND": "description",
                        "US_IS_ADDRESSBOOK": True,
                        "US_AUTO_SEARCH": False,
                        "US_AUTO_QUERY_LIMIT": 0,
                        "US_HAS_RESOURCE": True,
                        "US_RESOURCE_MULTIBOOKING": "departmentNumber"
                    }
                },
                "USER_MODULE_SETTINGS": {
                    "SOGO_D_MODULE_ACCESS": [
                        "mail",
                        "calendar",
                        "contact"
                    ],
                    "SOGO_D_MAPI_ACCESS": False,
                    "SOGO_D_EAS_ACCESS": False,
                    "SOGO_D_AUTOCOMPLETION_MIN_LEN": 2,
                    "SOGO_D_API_MAX_REQUEST": 0,
                    "SOGO_D_API_MAX_REQUEST_INTERVAL": 30,
                    "SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL": 300,
                    "SOGO_D_IDENTITIES_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED": True,
                    "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT": True,
                    "SOGO_D_SIGNATURE_SIZE_LIMIT": 200,
                    "SOGO_D_ALLOW_EXT_AVATAR": True,
                    "SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED": [
                        0,
                        1,
                        2,
                        5,
                        10,
                        20,
                        30,
                        60
                    ]
                },
                "MAIL_SETTINGS": {
                    "SOGO_D_MAIL_SERVER_TYPE": "imap",
                    "SOGO_D_IMAP_SERVER": "dovecot",
                    "SOGO_D_IMAP_PORT": 143,
                    "SOGO_D_SOFT_EMAIL_QUOTA": 1,
                    "SOGO_D_MAIL_PURGE_ALLOW": True,
                    "SOGO_D_MAIL_PURGE_MIN_DATE": 0,
                    "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
                    "SOGO_D_JITSI_LINK_ENABLED": True,
                    "SOGO_D_REMINDER_ALLOW_MAIL": True,
                    "SOGO_D_MAIL_FILTERING_ENABLED": True,
                    "SOGO_D_MAIL_FILTERING_TYPE": "sieve",
                    "SOGO_D_SIEVE_SERVER": "dovecot",
                    "SOGO_D_SIEVE_PORT": 4190,
                    "SOGO_D_SIEVE_FOLDER_ENCODING": "utf-7",
                    "SOGO_D_VACATION_ENABLED": True,
                    "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS": False,
                    "SOGO_D_FORWARD_ENABLED": True,
                    "SOGO_D_FORWARD_ALLOW_USER_DOMAIN": True,
                    "SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN": True,
                    "SOGO_D_FORWARD_ALLOW_EXT_DOMAIN": True,
                    "SOGO_D_NOTIFY_ENABLED": True,
                    "SOGO_D_NOTIFY_ALLOW_USER_DOMAIN": True,
                    "SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN": True,
                    "SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN": True,
                    "SOGO_D_MAIL_OUTGOING_TYPE": "smtp",
                    "SOGO_D_SMTP_SERVER": "postfix",
                    "SOGO_D_SMTP_PORT": 584,
                    "SOGO_D_SMTP_MASTER_ENABLED": False,
                    "SOGO_D_MAIL_MAX_SUBMISSION": 0,
                    "SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL": 30,
                    "SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl": 300,
                    "SOGO_D_MAIL_MAX_RECIPIENT": 0
                },
                "CALENDAR_CONTACT_SETTINGS": {
                    "SOGO_D_CALDAV_ENABLED": True,
                    "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE": False,
                    "SOGO_D_CALDAV_START_TIME": 0,
                    "SOGO_D_CARDAV_ENABLED": True,
                    "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
                    "SOGO_D_JITSI_LINK_ENABLED": True,
                    "SOGO_D_REMINDER_ALLOW_MAIL": True
                }
            }
        }

class AdminConfigDefaultDomainPatchSchema(Schema):
    """
    Schema for PATCH on /domain-default
    """

    settings  = fields.Dict(required=True, keys=fields.String(), values=fields.Raw())

    @classmethod
    def example(cls) -> dict:
        """Example of the schema

        :return: Example data
        :rtype: dict
        """
        return {
            "settings": {
                    "AUTH_SETTINGS": {
                        "SOGO_D_AUTH_TYPE": "plain",
                        "SOGO_D_PWD_CHANGE_ENABLED": True,
                        "SOGO_D_PWD_RECOVERY": True,
                        "SOGO_D_PWD_RECOVERY_METHOD": [
                            "secretQuestion",
                            "secondaryEmail"
                        ],
                        "SOGO_D_PWD_RECOVERY_FORCE": False,
                        "SOGO_D_PWD_RECOVERY_DELAY": 86400,
                        "SOGO_D_LOGIN_MFA": True,
                        "SOGO_D_LOGIN_MFA_METHOD": [
                            "totp"
                        ],
                        "SOGO_D_LOGIN_MFA_FORCE": False
                    },
                    "USER_SOURCE": {
                        "us_french": {
                            "US_UID": "ldap_ex",
                            "US_NAME": "us_french",
                            "US_TYPE": "ldap",
                            "US_LDAP_HOSTNAME": "ldap://openldap:390",
                            "US_LDAP_BIND_DN": "cn=admin,dc=example,dc=org",
                            "US_LDAP_BIND_DN_PWD": "password",
                            "US_LDAP_BASE_DN": "ou=users,dc=example,dc=org",
                            "US_LDAP_UID": "uid",
                            "US_LDAP_CN": "cn",
                            "US_LDAP_ID": "uid",
                            "US_LDAP_SCOPE": "SUB",
                            "US_LDAP_QUERY_TIMEOUT": 0,
                            "US_LDAP_BIND_AS_USER": False,
                            "US_LDAP_ATTR_FIELD": [
                                "*"
                            ],
                            "US_LDAP_GROUP_CLASS": [
                                "group",
                                "groupOfNames",
                                "groupOfUniqueNames",
                                "posixGroup"
                            ],
                            "US_CAN_AUTH": True,
                            "US_PWD_POLICY": False,
                            "US_PWD_LEN_MIN": 3,
                            "US_PWD_LEN_MAX": 0,
                            "US_MAIL": [
                                "mail"
                            ],
                            "US_KIND": "description",
                            "US_IS_ADDRESSBOOK": True,
                            "US_AUTO_SEARCH": False,
                            "US_AUTO_QUERY_LIMIT": 0,
                            "US_HAS_RESOURCE": True,
                            "US_RESOURCE_MULTIBOOKING": "departmentNumber"
                        }
                    },
                    "USER_MODULE_SETTINGS": {
                        "SOGO_D_MODULE_ACCESS": [
                            "mail",
                            "calendar",
                            "contact"
                        ],
                        "SOGO_D_MAPI_ACCESS": False,
                        "SOGO_D_EAS_ACCESS": False,
                        "SOGO_D_AUTOCOMPLETION_MIN_LEN": 2,
                        "SOGO_D_API_MAX_REQUEST": 0,
                        "SOGO_D_API_MAX_REQUEST_INTERVAL": 30,
                        "SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL": 300,
                        "SOGO_D_IDENTITIES_ENABLED": True,
                        "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED": True,
                        "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED": True,
                        "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED": True,
                        "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT": True,
                        "SOGO_D_SIGNATURE_SIZE_LIMIT": 200,
                        "SOGO_D_ALLOW_EXT_AVATAR": True,
                        "SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED": [
                            0,
                            1,
                            2,
                            5,
                            10,
                            20,
                            30,
                            60
                        ]
                    },
                    "MAIL_SETTINGS": {
                        "SOGO_D_MAIL_SERVER_TYPE": "imap",
                        "SOGO_D_IMAP_SERVER": "dovecot",
                        "SOGO_D_IMAP_PORT": 143,
                        "SOGO_D_SOFT_EMAIL_QUOTA": 1,
                        "SOGO_D_MAIL_PURGE_ALLOW": True,
                        "SOGO_D_MAIL_PURGE_MIN_DATE": 0,
                        "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
                        "SOGO_D_JITSI_LINK_ENABLED": True,
                        "SOGO_D_REMINDER_ALLOW_MAIL": True,
                        "SOGO_D_MAIL_FILTERING_ENABLED": True,
                        "SOGO_D_MAIL_FILTERING_TYPE": "sieve",
                        "SOGO_D_SIEVE_SERVER": "dovecot",
                        "SOGO_D_SIEVE_PORT": 4190,
                        "SOGO_D_SIEVE_FOLDER_ENCODING": "utf-7",
                        "SOGO_D_VACATION_ENABLED": True,
                        "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS": False,
                        "SOGO_D_FORWARD_ENABLED": True,
                        "SOGO_D_FORWARD_ALLOW_USER_DOMAIN": True,
                        "SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN": True,
                        "SOGO_D_FORWARD_ALLOW_EXT_DOMAIN": True,
                        "SOGO_D_NOTIFY_ENABLED": True,
                        "SOGO_D_NOTIFY_ALLOW_USER_DOMAIN": True,
                        "SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN": True,
                        "SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN": True,
                        "SOGO_D_MAIL_OUTGOING_TYPE": "smtp",
                        "SOGO_D_SMTP_SERVER": "postfix",
                        "SOGO_D_SMTP_PORT": 584,
                        "SOGO_D_SMTP_MASTER_ENABLED": False,
                        "SOGO_D_MAIL_MAX_SUBMISSION": 0,
                        "SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL": 30,
                        "SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl": 300,
                        "SOGO_D_MAIL_MAX_RECIPIENT": 0
                    },
                    "CALENDAR_CONTACT_SETTINGS": {
                        "SOGO_D_CALDAV_ENABLED": True,
                        "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE": False,
                        "SOGO_D_CALDAV_START_TIME": 0,
                        "SOGO_D_CARDAV_ENABLED": True,
                        "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
                        "SOGO_D_JITSI_LINK_ENABLED": True,
                        "SOGO_D_REMINDER_ALLOW_MAIL": True
                    }
                }
        }

class AdminConfigDomainGetData(Schema):
    """
    Data for GET domain

    :param Schema: _description_
    :type Schema: _type_
    :return: _description_
    :rtype: _type_
    """
    domain_name = fields.String(load_default="default", dump_default="default")
    domain_description = fields.String()
    domain_info = fields.Dict()
    settings  = fields.Dict(required=True, keys=fields.String(), values=fields.Raw())


class AdminConfigDomainGetSchema(ApiBaseResponse):
    """
    Sceham for GET domain

    :param ApiBaseResponse: _description_
    :type ApiBaseResponse: _type_
    """

    data = fields.Nested(AdminConfigDynamicFormData)

    @staticmethod
    def sort_by_values() -> set:
        """
        return values available for sorting by
        """
        return {"domain_name"}

    @staticmethod
    def filter_by_values() -> set:
        """
        return values available for sorting by
        """
        return {"domain_name", "domain_description", "domain_info", "domain_settings", "domain_origins"}

    @classmethod
    def example(cls) -> dict:
        """
        Example of data for the post request

        :return: Example data
        :rtype: dictAdminConfigDomainPostSchema
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": [{
                "domain_name": "default",
                "domain_description": "This is a domain configuration",
                "domain_info": "French ldap server",
                "domain_settings": {
                    "AUTH_SETTINGS": {
                        "SOGO_D_AUTH_TYPE": "plain",
                        "SOGO_D_PWD_CHANGE_ENABLED": True,
                        "SOGO_D_PWD_RECOVERY": True,
                        "SOGO_D_PWD_RECOVERY_METHOD": [
                            "secretQuestion",
                            "secondaryEmail"
                        ],
                        "SOGO_D_PWD_RECOVERY_FORCE": False,
                        "SOGO_D_PWD_RECOVERY_DELAY": 86400,
                        "SOGO_D_LOGIN_MFA": True,
                        "SOGO_D_LOGIN_MFA_METHOD": [
                            "totp"
                        ],
                        "SOGO_D_LOGIN_MFA_FORCE": False
                    },
                    "USER_SOURCE": {
                        "us_french": {
                            "US_UID": "ldap_ex",
                            "US_NAME": "us_french",
                            "US_TYPE": "ldap",
                            "US_LDAP_HOSTNAME": "ldap://openldap:390",
                            "US_LDAP_BIND_DN": "cn=admin,dc=example,dc=org",
                            "US_LDAP_BIND_DN_PWD": "password",
                            "US_LDAP_BASE_DN": "ou=users,dc=example,dc=org",
                            "US_LDAP_UID": "uid",
                            "US_LDAP_CN": "cn",
                            "US_LDAP_ID": "uid",
                            "US_LDAP_SCOPE": "SUB",
                            "US_LDAP_QUERY_TIMEOUT": 0,
                            "US_LDAP_BIND_AS_USER": False,
                            "US_LDAP_ATTR_FIELD": [
                                "*"
                            ],
                            "US_LDAP_GROUP_CLASS": [
                                "group",
                                "groupOfNames",
                                "groupOfUniqueNames",
                                "posixGroup"
                            ],
                            "US_CAN_AUTH": True,
                            "US_PWD_POLICY": False,
                            "US_PWD_LEN_MIN": 3,
                            "US_PWD_LEN_MAX": 0,
                            "US_MAIL": [
                                "mail"
                            ],
                            "US_KIND": "description",
                            "US_IS_ADDRESSBOOK": True,
                            "US_AUTO_SEARCH": False,
                            "US_AUTO_QUERY_LIMIT": 0,
                            "US_HAS_RESOURCE": True,
                            "US_RESOURCE_MULTIBOOKING": "departmentNumber"
                        }
                    },
                    "USER_MODULE_SETTINGS": {
                        "SOGO_D_MODULE_ACCESS": [
                            "mail",
                            "calendar",
                            "contact"
                        ],
                        "SOGO_D_MAPI_ACCESS": False,
                        "SOGO_D_EAS_ACCESS": False,
                        "SOGO_D_AUTOCOMPLETION_MIN_LEN": 2,
                        "SOGO_D_API_MAX_REQUEST": 0,
                        "SOGO_D_API_MAX_REQUEST_INTERVAL": 30,
                        "SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL": 300,
                        "SOGO_D_IDENTITIES_ENABLED": True,
                        "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED": True,
                        "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED": True,
                        "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED": True,
                        "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT": True,
                        "SOGO_D_SIGNATURE_SIZE_LIMIT": 200,
                        "SOGO_D_ALLOW_EXT_AVATAR": True,
                        "SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED": [
                            0,
                            1,
                            2,
                            5,
                            10,
                            20,
                            30,
                            60
                        ]
                    },
                    "MAIL_SETTINGS": {
                        "SOGO_D_MAIL_SERVER_TYPE": "imap",
                        "SOGO_D_IMAP_SERVER": "dovecot",
                        "SOGO_D_IMAP_PORT": 143,
                        "SOGO_D_SOFT_EMAIL_QUOTA": 1,
                        "SOGO_D_MAIL_PURGE_ALLOW": True,
                        "SOGO_D_MAIL_PURGE_MIN_DATE": 0,
                        "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
                        "SOGO_D_JITSI_LINK_ENABLED": True,
                        "SOGO_D_REMINDER_ALLOW_MAIL": True,
                        "SOGO_D_MAIL_FILTERING_ENABLED": True,
                        "SOGO_D_MAIL_FILTERING_TYPE": "sieve",
                        "SOGO_D_SIEVE_SERVER": "dovecot",
                        "SOGO_D_SIEVE_PORT": 4190,
                        "SOGO_D_SIEVE_FOLDER_ENCODING": "utf-7",
                        "SOGO_D_VACATION_ENABLED": True,
                        "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS": False,
                        "SOGO_D_FORWARD_ENABLED": True,
                        "SOGO_D_FORWARD_ALLOW_USER_DOMAIN": True,
                        "SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN": True,
                        "SOGO_D_FORWARD_ALLOW_EXT_DOMAIN": True,
                        "SOGO_D_NOTIFY_ENABLED": True,
                        "SOGO_D_NOTIFY_ALLOW_USER_DOMAIN": True,
                        "SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN": True,
                        "SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN": True,
                        "SOGO_D_MAIL_OUTGOING_TYPE": "smtp",
                        "SOGO_D_SMTP_SERVER": "postfix",
                        "SOGO_D_SMTP_PORT": 584,
                        "SOGO_D_SMTP_MASTER_ENABLED": False,
                        "SOGO_D_MAIL_MAX_SUBMISSION": 0,
                        "SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL": 30,
                        "SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl": 300,
                        "SOGO_D_MAIL_MAX_RECIPIENT": 0
                    },
                    "CALENDAR_CONTACT_SETTINGS": {
                        "SOGO_D_CALDAV_ENABLED": True,
                        "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE": False,
                        "SOGO_D_CALDAV_START_TIME": 0,
                        "SOGO_D_CARDAV_ENABLED": True,
                        "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
                        "SOGO_D_JITSI_LINK_ENABLED": True,
                        "SOGO_D_REMINDER_ALLOW_MAIL": True
                    }
                }
            }]
        }


class AdminConfigDomainPostSchema(Schema):
    """
    Schema of the body expected for posting default domain settings
    """
    domain_name = fields.String(load_default="default", dump_default="default")
    domain_description = fields.String()
    domain_info = fields.Dict()
    settings  = fields.Dict(keys=fields.String(), values=fields.Raw())

    @classmethod
    def example(cls) -> dict:
        """
        Example of data for the post request

        :return: Example data
        :rtype: dict
        """
        return {
            "domain_name": "default",
            "domain_description": "This is a domain configuration",
            "settings": {
                "AUTH_SETTINGS": {
                    "SOGO_D_AUTH_TYPE": "plain",
                    "SOGO_D_PWD_CHANGE_ENABLED": True,
                    "SOGO_D_PWD_RECOVERY": True,
                    "SOGO_D_PWD_RECOVERY_METHOD": [
                        "secretQuestion",
                        "secondaryEmail"
                    ],
                    "SOGO_D_PWD_RECOVERY_FORCE": False,
                    "SOGO_D_PWD_RECOVERY_DELAY": 86400,
                    "SOGO_D_LOGIN_MFA": True,
                    "SOGO_D_LOGIN_MFA_METHOD": [
                        "totp"
                    ],
                    "SOGO_D_LOGIN_MFA_FORCE": False
                },
                "USER_SOURCE": {
                    "us_french": {
                        "US_UID": "ldap_ex",
                        "US_NAME": "french",
                        "US_TYPE": "ldap",
                        "US_LDAP_HOSTNAME": "ldap://openldap:390",
                        "US_LDAP_BIND_DN": "cn=admin,dc=example,dc=org",
                        "US_LDAP_BIND_DN_PWD": "password",
                        "US_LDAP_BASE_DN": "ou=users,dc=example,dc=org",
                        "US_LDAP_UID": "uid",
                        "US_LDAP_CN": "cn",
                        "US_LDAP_ID": "uid",
                        "US_LDAP_SCOPE": "SUB",
                        "US_LDAP_QUERY_TIMEOUT": 0,
                        "US_LDAP_BIND_AS_USER": False,
                        "US_LDAP_ATTR_FIELD": [
                            "*"
                        ],
                        "US_LDAP_GROUP_CLASS": [
                            "group",
                            "groupOfNames",
                            "groupOfUniqueNames",
                            "posixGroup"
                        ],
                        "US_CAN_AUTH": True,
                        "US_PWD_POLICY": False,
                        "US_PWD_LEN_MIN": 3,
                        "US_PWD_LEN_MAX": 0,
                        "US_MAIL": [
                            "mail"
                        ],
                        "US_KIND": "description",
                        "US_IS_ADDRESSBOOK": True,
                        "US_AUTO_SEARCH": False,
                        "US_AUTO_QUERY_LIMIT": 0,
                        "US_HAS_RESOURCE": True,
                        "US_RESOURCE_MULTIBOOKING": "departmentNumber"
                    }
                },
                "USER_MODULE_SETTINGS": {
                    "SOGO_D_MODULE_ACCESS": [
                        "mail",
                        "calendar",
                        "contact"
                    ],
                    "SOGO_D_MAPI_ACCESS": False,
                    "SOGO_D_EAS_ACCESS": False,
                    "SOGO_D_AUTOCOMPLETION_MIN_LEN": 2,
                    "SOGO_D_API_MAX_REQUEST": 0,
                    "SOGO_D_API_MAX_REQUEST_INTERVAL": 30,
                    "SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL": 300,
                    "SOGO_D_IDENTITIES_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED": True,
                    "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT": True,
                    "SOGO_D_SIGNATURE_SIZE_LIMIT": 200,
                    "SOGO_D_ALLOW_EXT_AVATAR": True,
                    "SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED": [
                        0,
                        1,
                        2,
                        5,
                        10,
                        20,
                        30,
                        60
                    ]
                },
                "MAIL_SETTINGS": {
                    "SOGO_D_MAIL_SERVER_TYPE": "imap",
                    "SOGO_D_IMAP_SERVER": "dovecot",
                    "SOGO_D_IMAP_PORT": 143,
                    "SOGO_D_SOFT_EMAIL_QUOTA": 1,
                    "SOGO_D_MAIL_PURGE_ALLOW": True,
                    "SOGO_D_MAIL_PURGE_MIN_DATE": 0,
                    "SOGO_D_MAIL_FILTERING_ENABLED": True,
                    "SOGO_D_MAIL_FILTERING_TYPE": "sieve",
                    "SOGO_D_SIEVE_SERVER": "dovecot",
                    "SOGO_D_SIEVE_PORT": 4190,
                    "SOGO_D_SIEVE_FOLDER_ENCODING": "utf-7",
                    "SOGO_D_VACATION_ENABLED": True,
                    "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS": False,
                    "SOGO_D_FORWARD_ENABLED": True,
                    "SOGO_D_FORWARD_ALLOW_USER_DOMAIN": True,
                    "SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN": True,
                    "SOGO_D_FORWARD_ALLOW_EXT_DOMAIN": True,
                    "SOGO_D_NOTIFY_ENABLED": True,
                    "SOGO_D_NOTIFY_ALLOW_USER_DOMAIN": True,
                    "SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN": True,
                    "SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN": True,
                    "SOGO_D_MAIL_OUTGOING_TYPE": "smtp",
                    "SOGO_D_SMTP_SERVER": "postfix",
                    "SOGO_D_SMTP_PORT": 584,
                    "SOGO_D_SMTP_MASTER_ENABLED": False,
                    "SOGO_D_MAIL_MAX_SUBMISSION": 0,
                    "SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL": 30,
                    "SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl": 300,
                    "SOGO_D_MAIL_MAX_RECIPIENT": 0
                },
                "CALENDAR_CONTACT_SETTINGS": {
                    "SOGO_D_CALDAV_ENABLED": True,
                    "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE": False,
                    "SOGO_D_CALDAV_START_TIME": 0,
                    "SOGO_D_CARDAV_ENABLED": True,
                    "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
                    "SOGO_D_JITSI_LINK_ENABLED": True,
                    "SOGO_D_REMINDER_ALLOW_MAIL": True
                }
            }
        }

class AdminConfigDomainPatchSchema(Schema):
    """
    Schema of the body expected for posting default domain settings
    """
    domain_description = fields.String()
    domain_info = fields.Dict()
    settings  = fields.Dict(keys=fields.String(), values=fields.Raw())

    @classmethod
    def example(cls) -> dict:
        """
        Example of data for the post request

        :return: Example data
        :rtype: dict
        """
        return {
            "domain_description": "This is a domain configuration",
            "domain_info": {"mail_server": "imap french",
                             "user source": "sql french"},
            "settings": {
                "AUTH_SETTINGS": {
                    "SOGO_D_AUTH_TYPE": "plain",
                    "SOGO_D_PWD_CHANGE_ENABLED": True,
                    "SOGO_D_PWD_RECOVERY": True,
                    "SOGO_D_PWD_RECOVERY_METHOD": [
                        "secretQuestion",
                        "secondaryEmail"
                    ],
                    "SOGO_D_PWD_RECOVERY_FORCE": False,
                    "SOGO_D_PWD_RECOVERY_DELAY": 86400,
                    "SOGO_D_LOGIN_MFA": True,
                    "SOGO_D_LOGIN_MFA_METHOD": [
                        "totp"
                    ],
                    "SOGO_D_LOGIN_MFA_FORCE": False
                },
                "USER_SOURCE": {
                    "us_french": {
                        "US_UID": "ldap_ex",
                        "US_NAME": "french",
                        "US_TYPE": "ldap",
                        "US_LDAP_HOSTNAME": "ldap://openldap:390",
                        "US_LDAP_BIND_DN": "cn=admin,dc=example,dc=org",
                        "US_LDAP_BIND_DN_PWD": "password",
                        "US_LDAP_BASE_DN": "ou=users,dc=example,dc=org",
                        "US_LDAP_UID": "uid",
                        "US_LDAP_CN": "cn",
                        "US_LDAP_ID": "uid",
                        "US_LDAP_SCOPE": "SUB",
                        "US_LDAP_QUERY_TIMEOUT": 0,
                        "US_LDAP_BIND_AS_USER": False,
                        "US_LDAP_ATTR_FIELD": [
                            "*"
                        ],
                        "US_LDAP_GROUP_CLASS": [
                            "group",
                            "groupOfNames",
                            "groupOfUniqueNames",
                            "posixGroup"
                        ],
                        "US_CAN_AUTH": True,
                        "US_PWD_POLICY": False,
                        "US_PWD_LEN_MIN": 3,
                        "US_PWD_LEN_MAX": 0,
                        "US_MAIL": [
                            "mail"
                        ],
                        "US_KIND": "description",
                        "US_IS_ADDRESSBOOK": True,
                        "US_AUTO_SEARCH": False,
                        "US_AUTO_QUERY_LIMIT": 0,
                        "US_HAS_RESOURCE": True,
                        "US_RESOURCE_MULTIBOOKING": "departmentNumber"
                    }
                },
                "USER_MODULE_SETTINGS": {
                    "SOGO_D_MODULE_ACCESS": [
                        "mail",
                        "calendar",
                        "contact"
                    ],
                    "SOGO_D_MAPI_ACCESS": False,
                    "SOGO_D_EAS_ACCESS": False,
                    "SOGO_D_AUTOCOMPLETION_MIN_LEN": 2,
                    "SOGO_D_API_MAX_REQUEST": 0,
                    "SOGO_D_API_MAX_REQUEST_INTERVAL": 30,
                    "SOGO_D_API_MAX_REQUEST_BLOCK_INTERVAL": 300,
                    "SOGO_D_IDENTITIES_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED": True,
                    "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED": True,
                    "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT": True,
                    "SOGO_D_SIGNATURE_SIZE_LIMIT": 200,
                    "SOGO_D_ALLOW_EXT_AVATAR": True,
                    "SOGO_D_MAIL_REFRESH_INTERVAL_ALLOWED": [
                        0,
                        1,
                        2,
                        5,
                        10,
                        20,
                        30,
                        60
                    ]
                },
                "MAIL_SETTINGS": {
                    "SOGO_D_MAIL_SERVER_TYPE": "imap",
                    "SOGO_D_IMAP_SERVER": "dovecot",
                    "SOGO_D_IMAP_PORT": 143,
                    "SOGO_D_SOFT_EMAIL_QUOTA": 1,
                    "SOGO_D_MAIL_PURGE_ALLOW": True,
                    "SOGO_D_MAIL_PURGE_MIN_DATE": 0,
                    "SOGO_D_MAIL_FILTERING_ENABLED": True,
                    "SOGO_D_MAIL_FILTERING_TYPE": "sieve",
                    "SOGO_D_SIEVE_SERVER": "dovecot",
                    "SOGO_D_SIEVE_PORT": 4190,
                    "SOGO_D_SIEVE_FOLDER_ENCODING": "utf-7",
                    "SOGO_D_VACATION_ENABLED": True,
                    "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS": False,
                    "SOGO_D_FORWARD_ENABLED": True,
                    "SOGO_D_FORWARD_ALLOW_USER_DOMAIN": True,
                    "SOGO_D_FORWARD_ALLOW_SOGO_DOMAIN": True,
                    "SOGO_D_FORWARD_ALLOW_EXT_DOMAIN": True,
                    "SOGO_D_NOTIFY_ENABLED": True,
                    "SOGO_D_NOTIFY_ALLOW_USER_DOMAIN": True,
                    "SOGO_D_NOTIFY_ALLOW_SOGO_DOMAIN": True,
                    "SOGO_D_NOTIFY_ALLOW_EXT_DOMAIN": True,
                    "SOGO_D_MAIL_OUTGOING_TYPE": "smtp",
                    "SOGO_D_SMTP_SERVER": "postfix",
                    "SOGO_D_SMTP_PORT": 584,
                    "SOGO_D_SMTP_MASTER_ENABLED": False,
                    "SOGO_D_MAIL_MAX_SUBMISSION": 0,
                    "SOGO_D_MAIL_MAX_SUBMISSION_INTERVAL": 30,
                    "SOGO_D_MAIL_MAX_SUBMISSION_BLOCK_INTERVAl": 300,
                    "SOGO_D_MAIL_MAX_RECIPIENT": 0
                },
                "CALENDAR_CONTACT_SETTINGS": {
                    "SOGO_D_CALDAV_ENABLED": True,
                    "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE": False,
                    "SOGO_D_CALDAV_START_TIME": 0,
                    "SOGO_D_CARDAV_ENABLED": True,
                    "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
                    "SOGO_D_JITSI_LINK_ENABLED": True,
                    "SOGO_D_REMINDER_ALLOW_MAIL": True
                }
            }
        }
