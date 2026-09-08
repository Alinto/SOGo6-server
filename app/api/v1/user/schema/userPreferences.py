from marshmallow import Schema, fields, validate

from app.utils.api.ApiBaseResponse import ApiBaseResponse

class UserPeferencesGetRetSchema(ApiBaseResponse):
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
            "USER_GENERAL": {
                "SOGO_U_LANGUAGE": "English",
                "SOGO_U_TIME_FORMAT": "HH:mm",
                "SOGO_U_FIRST_MODULE": "mail",
                "SOGO_U_BROWSER_NOTIF": False,
                "SOGO_U_REFRESH_MAIL_VIEW": 0,
                "SOGO_U_EXT_AVATAR_ENABLED": False,
                "SOGO_U_PROFILE_PICTURE": "default"
            },
            "USER_SECURITY": {
                "SOGO_U_MFA_ENABLE": False
            },
            "USER_CONTACT_GENERAL": {
                "SOGO_U_ADDRESSBOOK_CREATION_NOTIF": True
            },
            "USER_CALENDAR_GENERAL": {
                "SOGO_U_NO_INVITATION": False,
                "SOGO_U_BUSY_OFF_HOURS": False,
                "SOGO_U_CALENDAR_DEFAULT": "SOGO_DEFAULT_CALENDAR",
                "SOGO_U_WORKDAY_END_TIME": "18:00",
                "SOGO_U_TASK_DEFAULT_CLASS": "PUBLIC",
                "SOGO_U_WORKDAY_START_TIME": "09:00",
                "SOGO_U_EVENT_DEFAULT_CLASS": "PUBLIC",
                "SOGO_U_CALENDAR_DAYS_SHOWED": [
                0,
                1,
                2,
                3,
                4,
                5,
                6
                ],
                "SOGO_U_JOURNAL_DEFAULT_CLASS": "PUBLIC",
                "SOGO_U_TASK_DEFAULT_REMINDER": "-PT15M",
                "SOGO_U_EVENT_DEFAULT_REMINDER": "-PT15M",
                "SOGO_U_CALENDAR_CREATION_NOTIF": True,
                "SOGO_U_CALENDAR_VIEW_FIRST_DAY": 0,
                "SOGO_U_JOURNAL_DEFAULT_REMINDER": "-PT15M",
                "SOGO_U_DAV_FORCE_SYNC_FROM_CLIENT": False,
                "SOGO_U_DO_NOT_SEND_INVIT_FROM_DAV": False,
                "SOGO_U_CALENDAR_WEEK_NUMBER_FORMAT": "%U"
            },
            "USER_CONTACT_CATEGORY": {},
            "USER_CALENDAR_CATEGORY": {},
            "USER_MAIL_GENERAL_SETTINGS": {}
        }

class UserPreferencesPatch(Schema):
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
                "USER_GENERAL": {
                    "SOGO_U_LANGUAGE": "French",
                }
            }
        }

class UserPreferencesFoldersPatch(Schema):
    """
    Schema of the body expected for PATCH /preferences/folders

    Updates a single folder key's boolean value within the folders column (CALENDAR or ADDRESSBOOKS)
    """
    resource = fields.String(required=True, validate=validate.OneOf(["CALENDAR", "ADDRESSBOOKS"]))
    id = fields.String(required=True)
    value = fields.Boolean(required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example of data for the patch request

        :return: Example data
        :rtype: dict
        """
        return {
            "resource": "CALENDAR",
            "id": "3c4b0bc9-3aab-4243-abb2-75a5edc8c239",
            "value": True
        }