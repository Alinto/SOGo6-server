# -*- coding: utf-8 -*-

"""
Defines all users parameters
"""
from typing import Type
from marshmallow import fields, validate
from app.config.settings.SogoSchema import SogoSchema
from app.utils.config.generateObjFromSchema import SettingsObj

import zoneinfo

from marshmallow import Schema, fields, validate, validates_schema, ValidationError

TIMEZONES = zoneinfo.available_timezones()


class UserGeneralSettings(SogoSchema):
    """
    Schema for user general settings
    """

    subparent = "USER_GENERAL"



    #Language #TODO do we need to validate available language here? Or this is just frontend work?
    SOGO_U_LANGUAGE = fields.String(load_default="English", dump_default="English")
    #Timezone #TODO the timezones depends of the OS system and may be incomplete -> read https://docs.python.org/3/library/zoneinfo.html
    SOGO_U_TIMEZONE = fields.String(validate=validate.OneOf(TIMEZONES))
    #Python format -> https://docs.python.org/3.6/library/datetime.html#strftime-strptime-behavior
    #React format -> https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date-time-string-format 
    SOGO_U_TIME_FORMAT = fields.String(load_default="HH:mm", dump_default="HH:mm") #Value must be react-ready format
    SOGO_U_LONG_DATE = fields.String() #Format to show long date
    SOGO_U_SHORT_DATE = fields.String() #Format to show short date
    SOGO_U_FIRST_MODULE = fields.String(load_default="mail", dump_default="mail",
                                        validate=validate.OneOf(('mail', 'calendar', 'contact', 'last'))) #Tell what module to show after login
    SOGO_U_REFRESH_MAIL_VIEW = fields.Integer(load_default=0, dump_default=0, validate=validate.OneOf((0, 1, 2, 5, 10, 20, 30, 60))) #0 means the mail view must be refreshed manually, other value are the poolin interval in minutes
    SOGO_U_BROWSER_NOTIF = fields.Boolean(load_default=False, dump_default=False) #Enable notificaiton on browser
    SOGO_U_EXT_AVATAR_ENABLED  = fields.Boolean(load_default=False, dump_default=False) #Download external avatar (gravatar, libravatar)


class UserSecuritySettings(SogoSchema):
    """
    Schema for user security settings
    """

    subparent = "USER_SECURITY"

    #MFA -> May need more parameters enc check (E.g. totp needs to validate a code before accepting it)
    SOGO_U_MFA_ENABLE = fields.Boolean(load_default=False, dump_default=False) #Enable MFA for the user
    SOGO_U_MFA_METHOD = fields.String() #Choice of the method, values must be from SOGO_D_LOGIN_MFA_METHOD
    SOGO_U_MFA_PARAM = fields.Dict() #Dict with extra parameters for the MFA method if needed
    #Password recovery (#TODO encrypt all of that in the database)
    SOGO_U_PWD_RECOVERY = fields.String() #Must be None/empty or a value of SOGO_D_PWD_RECOVERY_METHOD
    SOGO_U_PWD_QUESTION = fields.String() #Written by the user
    SOGO_U_PWD_QUESTION_ANSWER = fields.String() # Anwser given by the user
    SOGO_U_PWD_SECOND_MAIL = fields.String() #Secondary mail for users

class UserCalendarGeneralSettings(SogoSchema):
    """
    Schema for user calendar general settings
    """

    subparent = "USER_CALENDAR_GENERAL"

    SOGO_U_CALENDAR_CREATION_NOTIF = fields.Boolean(load_default=True, dump_default=True) #Send mail notification when user create a calendar or addrebook
    SOGO_U_CALENDAR_VIEW_FIRST_DAY = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0, max=6)) #0 means Sunday, first day of the week showns in calendar weeks and months views.
    SOGO_U_WORKDAY_START_TIME = fields.String(load_default="09:00", dump_default="09:00") # Allow to define work hours
    SOGO_U_WORKDAY_END_TIME = fields.String(load_default="18:00", dump_default="18:00")  #
    SOGO_U_BUSY_OFF_HOURS = fields.Boolean(load_default=False, dump_default=False) # Be shown as busy outside work hour
    SOGO_U_CALENDAR_DAYS_SHOWED = fields.List(fields.Integer(validate=validate.Range(min=0, max=6)),
                                              load_default=[0,1,2,3,4,5,6],
                                              dump_default=[0,1,2,3,4,5,6]) #Days to show in calendar view; 0 Sunday, 6 Saturday
    SOGO_U_CALENDAR_WEEK_NUMBER_FORMAT = fields.String(load_default="%U",
                                                       dump_default="%U",
                                                       validate=validate.OneOf(('%U', '%W', '%V'))) #How the week number is evaluated
                                                                                                    #'First4DayWeek' -> '%V' in datetime format
                                                                                                    #'FirstFullWeek' -> either %U (first sunday) or %W (first monday)
    SOGO_U_CALENDAR_DEFAULT = fields.String(load_default="SOGO_DEFAULT_CALENDAR", dump_default="SOGO_DEFAULT_CALENDAR") #Default Calendar chosen when creating a new event
    SOGO_U_EVENT_DEFAULT_CLASS = fields.String(load_default="PUBLIC", dump_default="PUBLIC", validate=validate.OneOf(('PUBLIC', 'CONFIDENTIAL', 'PRIVATE')))
    SOGO_U_TASK_DEFAULT_CLASS = fields.String(load_default="PUBLIC", dump_default="PUBLIC", validate=validate.OneOf(('PUBLIC', 'CONFIDENTIAL', 'PRIVATE')))
    SOGO_U_JOURNAL_DEFAULT_CLASS = fields.String(load_default="PUBLIC", dump_default="PUBLIC", validate=validate.OneOf(('PUBLIC', 'CONFIDENTIAL', 'PRIVATE')))
    SOGO_U_EVENT_DEFAULT_REMINDER = fields.String(load_default="-PT15M", dump_default="-PT15M") #TODO was fixed choices of values in SOGO in icalendar format like '-PT5M' or '-PT1W'
    SOGO_U_TASK_DEFAULT_REMINDER = fields.String(load_default="-PT15M", dump_default="-PT15M") #TODO same as above
    SOGO_U_JOURNAL_DEFAULT_REMINDER = fields.String(load_default="-PT15M", dump_default="-PT15M") #TODO don't know if journal can have reminder?

    #Invitation
    SOGO_U_NO_INVITATION = fields.Boolean(load_default=False, dump_default=False) #Prevent user to be add as attendees by others users
    SOGO_U_NO_INVITATION_WHITELIST = fields.List(fields.String()) #List of user uid that can invite the user
    SOGO_U_DO_NOT_SEND_INVIT_FROM_DAV = fields.Boolean(load_default=False, dump_default=False) #Do not send invit mail notif when receiving a new event from caldav
                                                                                               #(Because the dav client already does it)
    
    #DAV
    SOGO_U_DAV_FORCE_SYNC_FROM_CLIENT  = fields.Boolean(load_default=False, dump_default=False) #If events from the client are more recent, force the sync anyway.


class UserCalendarCategorySettings(SogoSchema):
    """
    Schema for user caleandar category settings
    """

    subparent = "USER_CALENDAR_CATEGORY"

    #TODO tuple(name, color, is_default) color will HSL
    SOGO_U_CALENDAR_CATEGORIES = fields.List(fields.Tuple((fields.String(), fields.String(), fields.Boolean())))

class UserContactGeneralSettings(SogoSchema):
    """
    Schema for user contact general settings
    """

    subparent = "USER_CONTACT_GENERAL"

    SOGO_U_ADDRESSBOOK_CREATION_NOTIF = fields.Boolean(load_default=True, dump_default=True)

class ContactCategorySchema(Schema):
    """
    Schema for a single contact category
    """
    name = fields.String(required=True)
    color = fields.String(required=True)
    can_be_translated = fields.Boolean(required=True)


class UserContactCategorySettings(SogoSchema):
    """
    Schema for user contact category settings
    """

    subparent = "USER_CONTACT_CATEGORY"

    SOGO_U_CONTACT_CATEGORIES = fields.List(fields.Nested(ContactCategorySchema))


class UserMailViewSettings(SogoSchema):
    """
    Schema for user mail view
    """

    subparent = "USER_MAIL_VIEW_SETTINGS"

    #Mail view
    SOGO_U_DRAFT_FOLDER_NAME = fields.String(load_default="DRAFT", dump_default="DRAFT") #Name of the draft folder
    SOGO_U_SENT_FOLDER_NAME  = fields.String(load_default="SENT", dump_default="SENT") #Name of the sent folder
    SOGO_U_TRASH_FOLDER_NAME = fields.String(load_default="TRASH", dump_default="TRASH") #Name of the trash folder
    SOGO_U_JUNK_FOLDER_NAME  = fields.String(load_default="JUNK", dump_default="JUNK") #Name of the junk folder
    SOGO_U_TEMPLATE_FOLDER_NAME = fields.String(load_default="TEMPLATE", dump_default="TEMPLATE") #Name of the template folder

    #Mailfolder Subscribe
    SOGO_U_MAILFOLDER_NOT_SUB = fields.List(fields.String()) #list of mailfoder that the user don't follow (default empty list means it follow everything)

class UserMailGeneralSettings(SogoSchema):
    """
    Schema for user mail general settings
    """

    subparent = "USER_MAIL_GENERAL_SETTINGS"

    #General
    SOGO_U_ALLOW_MAILFOLDER_SUBSCRIBE = fields.Boolean(load_default=False, dump_default=False) #Allow or not the user to subscribe to dome folder only
    SOGO_U_SHOW_ALL_UNSEEN_COUNT = fields.Boolean(load_default=False, dump_default=False) #Detch the unseen counts for all folders and not only the selected one.
    SOGO_U_SORT_BY_THREAD = fields.Boolean(load_default=False, dump_default=False) #TODO check headers for mail id
    SOGO_U_MAIL_FORWARDING_FORMAT = fields.String(load_default="inline", dump_default="inline", validate=validate.OneOf(('inline', 'attachment')))
                                                        #Tell if the forwarded email is in the body or in attach file
    SOGO_U_ATTACHMENT_POSITION = fields.String(load_default="below", dump_default="below", validate=validate.OneOf(('below', 'above')))
    SOGO_U_HIDE_INLINE_ATTACHMENT = fields.Boolean(load_default=False, dump_default=False) #Do no show inline images as attachment file in the mail viewer
    SOGO_U_DISPLAY_REMOTE_INLINE = fields.Boolean(load_default=False, dump_default=False) #Do not ask user to download external image, do it autimaticcaly
                                                                                        #TODO not safe at all but sogo 5 allowed that...
                                                                                        #TODO image proxying?
    SOGO_U_REPLY_POSITION = fields.String(load_default="below", dump_default="below", validate=validate.OneOf(('below', 'above')))
                                                        #Tell if the quoted email is shown above or below the user answer
    SOGO_U_SIGNATURE_POSITION = fields.String(load_default="below", dump_default="below", validate=validate.OneOf(('below', 'above')))
                                                        #Tell if the signature is shown above or below the quoted email
    SOGO_U_USE_SIGNATURE = fields.List(fields.String(validate=validate.OneOf(('new', 'reply', 'forward'))),
                                       load_default=['new', 'reply', 'forward'],
                                       dump_default=['new', 'reply', 'forward'])
    SOGO_U_COMPOSE_MAIL_TYPE_DEFAULT = fields.String(load_default="html", dump_default="html", validate=validate.OneOf(('html', 'text'))) #TODO directly in the composer
    SOGO_U_COMPOSE_MAIL_WINDOW = fields.String(load_default="inline", dump_default="inline", validate=validate.OneOf(('inline', 'popup')))
                                    #Does the mail composer opens in a popup or on the webmail page.
    
    SOGO_U_MARK_READ_DELAY = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0)) #Delay in seconds before a mail is marked as read. 0 means no delay
    SOGO_U_DRAFT_AUTOSAVE = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0)) #Interval in seconds when a draft is autosave, 0 means save always #TODO how??
    SOGO_U_MAIL_ALLOW_RECEIPT = fields.Boolean(load_default=True, dump_default=True) #Allow mail to ask for receipts

    SOGO_U_COLLECT_UNKNWON_ADDRESSES = fields.Boolean(load_default=False, dump_default=False) #Collect address send to unknwon mail. (So next time it will be in autocompletion)
    SOGO_U_COLLECT_UNKNWON_ADDRESSBOOK_NAME = fields.String(load_default="Collected", dump_default="Collected") #Name of the collected addressbook if SOGO_U_COLLECT_UNKNWON_ADDRESSES=True



class UserMailCategorySettings(SogoSchema):
    """
    Schema for user mail category settings
    """

    subparent = "USER_MAIL_GENERAL_SETTINGS"

    #Categories (Nom, couleur, is_default)
    SOGO_U_MAIL_CATEGORIES = fields.List(fields.Tuple((fields.String(), fields.String(), fields.Boolean())))



class UserExtraSettings(SogoSchema):
    """
    Schema for user extra parameters.

    If any client/UI needs to store extra parameters, they should do it here.
    There will be no control and they will not affect in any way the backend behavior
    """

    subparent = "USER_MAIL_GENERAL_SETTINGS"
    #Extra parameters. No check on them, for UI that would need extra params not referenced here
    SOGO_U_EXTRA = fields.Dict()



def get_all_user_settings_schema() -> list[Type[SogoSchema]]:
    """
    Return a list with all Sogo Domain Schema classes

    :return: List with all domain schem classes
    :rtype: list[Type[SogoSchema]]
    """
    all_schemas = [UserGeneralSettings,
                   UserSecuritySettings,
                   UserCalendarGeneralSettings,
                   UserCalendarCategorySettings,
                   UserContactGeneralSettings,
                   UserContactCategorySettings,
                   UserMailGeneralSettings,
                   UserMailCategorySettings,
                   UserExtraSettings]
    return all_schemas

user_settings_dict : dict[str, Type[SogoSchema]] = {
    UserGeneralSettings.subparent.lower(): UserGeneralSettings,
    UserSecuritySettings.subparent.lower(): UserSecuritySettings,
    UserCalendarGeneralSettings.subparent.lower(): UserCalendarGeneralSettings,
    UserCalendarCategorySettings.subparent.lower(): UserCalendarCategorySettings,
    UserContactGeneralSettings.subparent.lower(): UserContactCategorySettings,
    UserMailGeneralSettings.subparent.lower(): UserMailGeneralSettings,
    UserMailCategorySettings.subparent.lower(): UserMailCategorySettings,
    UserMailViewSettings.subparent.lower(): UserMailViewSettings,
    UserExtraSettings.subparent.lower(): UserExtraSettings
}

def get_user_setting_scheme_for_subparent(subparent: str) -> None|Type[SogoSchema]:
    """
    Return the schema corresponding to the subparent

    :param subparent: _description_
    :type subparent: str
    :return: _description_
    :rtype: None|Type[SogoSchema]
    """

    return user_settings_dict.get(subparent, None)
