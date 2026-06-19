from marshmallow import Schema, fields

from app.utils.api.ApiBaseResponse import ApiBaseResponse

class UserProfileGetRetSchema(ApiBaseResponse):
    """
    Schema of the result GET /api/user/v1/preferences
    """
    data = fields.Dict(fields.String(), fields.Dict(fields.String(), fields.Raw()))

    @classmethod
    def example(cls) -> dict:
        """
        Example of result for GET /system

        :return: example
        :rtype: dict
        """
        return {
        "data": {
            "mailboxes": [
            {
                "certificates": {},
                "id": "0",
                "identities": [
                {
                    "isDefault": True,
                    "mail": "sogo-tests1@example.org",
                    "name": "John Paul",
                    "replyTo": "sogo-tests1@example.org",
                    "signatures": {}
                }
                ],
                "receipts": {}
            }
            ],
            "prefs": {
            "USER_CALENDAR_CATEGORY": {},
            "USER_CALENDAR_GENERAL": {
                "SOGO_U_BUSY_OFF_HOURS": False,
                "SOGO_U_CALENDAR_CREATION_NOTIF": True,
                "SOGO_U_CALENDAR_DAYS_SHOWED": [
                0,
                1,
                2,
                3,
                4,
                5,
                6
                ],
                "SOGO_U_CALENDAR_DEFAULT": "SOGO_DEFAULT_CALENDAR",
                "SOGO_U_CALENDAR_VIEW_FIRST_DAY": 0,
                "SOGO_U_CALENDAR_WEEK_NUMBER_FORMAT": "%U",
                "SOGO_U_DAV_FORCE_SYNC_FROM_CLIENT": False,
                "SOGO_U_DO_NOT_SEND_INVIT_FROM_DAV": False,
                "SOGO_U_EVENT_DEFAULT_CLASS": "PUBLIC",
                "SOGO_U_EVENT_DEFAULT_REMINDER": "-PT15M",
                "SOGO_U_JOURNAL_DEFAULT_CLASS": "PUBLIC",
                "SOGO_U_JOURNAL_DEFAULT_REMINDER": "-PT15M",
                "SOGO_U_NO_INVITATION": False,
                "SOGO_U_TASK_DEFAULT_CLASS": "PUBLIC",
                "SOGO_U_TASK_DEFAULT_REMINDER": "-PT15M",
                "SOGO_U_WORKDAY_END_TIME": "18:00",
                "SOGO_U_WORKDAY_START_TIME": "09:00"
            },
            "USER_CONTACT_CATEGORY": {},
            "USER_CONTACT_GENERAL": {
                "SOGO_U_ADDRESSBOOK_CREATION_NOTIF": True
            },
            "USER_GENERAL": {
                "SOGO_U_BROWSER_NOTIF": False,
                "SOGO_U_EXT_AVATAR_ENABLED": False,
                "SOGO_U_PROFILE_PICTURE": "default",
                "SOGO_U_FIRST_MODULE": "mail",
                "SOGO_U_LANGUAGE": "French",
                "SOGO_U_REFRESH_MAIL_VIEW": 0,
                "SOGO_U_TIME_FORMAT": "HH:mm"
            },
            "USER_MAIL_GENERAL_SETTINGS": {},
            "USER_SECURITY": {
                "SOGO_U_MFA_ENABLE": False
            }
            },
            "ui": {
            "SOGO_D_ALLOW_EXT_MAIL_ACCOUNT": True,
            "SOGO_D_AUTOCOMPLETION_MIN_LEN": 2,
            "SOGO_D_CALDAV_ENABLED": True,
            "SOGO_D_CALDAV_PUBLIC_ACCESS_ENABLE": False,
            "SOGO_D_CARDAV_ENABLED": True,
            "SOGO_D_CARDAV_PUBLIC_ACCESS_ENABLE": False,
            "SOGO_D_FOLDER_DISABLE_EXPORTSOGO_D_FOLDER_DISABLE_SHARING": None,
            "SOGO_D_FOLDER_DISABLE_SHARING_ANY_AUTH": None,
            "SOGO_D_FORWARD_ENABLED": True,
            "SOGO_D_IDENTITIES_CUSTOM_FROM_ENABLED": True,
            "SOGO_D_IDENTITIES_CUSTOM_NAME_ENABLED": True,
            "SOGO_D_IDENTITIES_CUSTOM_REPLY_TO_ENABLED": True,
            "SOGO_D_IDENTITIES_ENABLED": True,
            "SOGO_D_JITSI_BASE_URL": None,
            "SOGO_D_JITSI_LINK_ENABLED": True,
            "SOGO_D_LOGIN_MFA": True,
            "SOGO_D_LOGIN_MFA_METHOD": [
                "totp"
            ],
            "SOGO_D_MAIL_FILTERING_ENABLED": True,
            "SOGO_D_MAIL_MAX_RECIPIENT": 0,
            "SOGO_D_MAIL_PURGE_ALLOW": True,
            "SOGO_D_MAIL_PURGE_MIN_DATE": 0,
            "SOGO_D_MAIL_DRAFT_AUTOSAVE": 5,
            "SOGO_D_MODULE_ACCESS": [
                "mail",
                "calendar",
                "contact"
            ],
            "SOGO_D_NOTIFY_ENABLED": True,
            "SOGO_D_PWD_CHANGE_ENABLED": True,
            "SOGO_D_PWD_RECOVERY": True,
            "SOGO_D_PWD_RECOVERY_METHOD": [
                "secretQuestion",
                "secondaryEmail"
            ],
            "SOGO_D_REMINDER_ALLOW_MAIL": True,
            "SOGO_D_VACATION_ALLOW_RESPONSE_ALWAYS": False,
            "SOGO_D_VACATION_ENABLED": True,
            "US_AUTO_SEARCH": None,
            "US_PWD_DIGITS_MIN": None,
            "US_PWD_LEN_MAX": None,
            "US_PWD_LEN_MIN": None,
            "US_PWD_LOWERCASE_MIN": None,
            "US_PWD_POLICY": None,
            "US_PWD_SPECIAL_ALLOWED": None,
            "US_PWD_SPECIAL_MIN": None,
            "US_PWD_UPPERCASE_MIN": None
            }
        },
        "error_code": "S000000",
        "error_msg": "No Error"
        }