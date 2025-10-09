# -*- coding: utf-8 -*-

"""
Defines all users parameters
"""

import zoneinfo

from marshmallow import Schema, fields, validate, validates_schema, ValidationError

TIMEZONES = zoneinfo.available_timezones()

class UserSettings(Schema):
    """
    Schema for user settings
    """

    #Timezone #TODO the timezones depends of the OS system and may be incomplete -> read https://docs.python.org/3/library/zoneinfo.html
    SOGO_U_TIMEZONE = fields.String(validate=validate.OneOf(TIMEZONES))
    #Python format -> https://docs.python.org/3.6/library/datetime.html#strftime-strptime-behavior
    #React format -> https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date-time-string-format 
    SOGO_U_TIME_FORMAT = fields.String(load_default="HH:mm", dump_default="HH:mm") #Value must be react-ready format
    SOGO_U_CALENDAR_WEEK_NUMBER_FORMAT = fields.String(load_default="%U", dump_default="%U", validate=validate.OneOf(('%U', '%W', '%V'))) #How the week number is evaluated

    #Language #TODO do we need to validate available language here? Or this is just frontend work?
    SOGO_U_LANGUAGE = fields.String(load_default="English", dump_default="English")

    #Folders
    SOGO_U_FOLDER_CREATION_NOTIF = fields.Boolean(load_default=True, dump_default=True) #Send mail notification when user create a calenanr or addrebook
    SOGO_U_COLLECT_UNKNWON_ADDRESSES = fields.Boolean(load_default=False, dump_default=False) #Send mail notification when user create a calenanr or addrebook

    #Mail
    SOGO_U_GRAVATAR_ENABLED  = fields.Boolean() #Download gravatar pics
    SOGO_U_DRAFT_FOLDER_NAME = fields.String() #Name of the draft folder
    SOGO_U_SENT_FOLDER_NAME  = fields.String() #Name of the sent folder
    SOGO_U_TRASH_FOLDER_NAME = fields.String() #Name of the trash folder
    SOGO_U_JUNK_FOLDER_NAME  = fields.String() #Name of the junk folder
    SOGO_U_MAIL_FORWARDING_FORMAT = fields.String(load_default="inline", dump_default="inline", validate=validate.OneOf(('inline', 'attachment')))
                                                        #Tell if the forwarded email is in the body or in attach file
    SOGO_U_HIDE_INLINE_ATTACHMENT = fields.Boolean(load_default=False, dump_default=False) #Do no show inline images as attachment file in the mail viewer
    SOGO_U_REPLY_POSITION = fields.String(load_default="below", dump_default="below", validate=validate.OneOf(('below', 'above')))
                                                        #Tell if the quoted email is shown above or below the user answer
    SOGO_U_SIGNATURE_POSITION = fields.String(load_default="below", dump_default="below", validate=validate.OneOf(('below', 'above')))
                                                        #Tell if the signature is shown above or below the quoted email
    SOGO_U_USE_SIGNATURE = fields.List(fields.String(validate=validate.OneOf(('new', 'reply', 'forward'))),
                                       load_default=['new', 'reply', 'forward'],
                                       dump_default=['new', 'reply', 'forward'])
    SOGO_U_COMPOSE_MAIL_TYPE_DEFAULT = fields.String(load_default="html", dump_default="html", validate=validate.OneOf(('html', 'text')))
    SOGO_U_COMPOSE_MAIL_WINDOW = fields.String(load_default="inline", dump_default="inline", validate=validate.OneOf(('inline', 'popup')))
                                    #Does the mail composer open in a popup or on the webmail page.


    #DAV
    SOGO_U_DAV_FORCE_SYNC_FROM_CLIENT  = fields.Boolean(load_default=False, dump_default=False) #If events from the client are more recent, force the sync anyway.

    #Webpage
    SOGO_U_FIRST_MODULE = fields.String(load_default="mail", dump_default="mail", validate=validate.OneOf(('mail', 'calendar', 'contact', 'last')))
                                                                        #Tell what module to show after login
    SOGO_U_REFRESH_MAIL_VIEW = fields.Integer(load_default=0, dump_default=0, validate=validate.OneOf((0, 1, 2, 5, 10, 20, 30, 60))) #0 means the mail view must be refreshed manually, other value are the poolin interval in minutes

    #Calendar
    SOGO_U_CALENDAR_DEFAULT = fields.String() #Default calendar chosen when creating a new event
    SOGO_U_CALENDAR_VIEW_FIRST_DAY = fields.Integer(load_default=0, dump_default=0, validate=validate.Range(min=0, max=6)) #0 means Sunday, first day of the week showns in calendar weeks and motnhs views.
    SOGO_U_CALENDAR_CATEGORIES = fields.List(fields.Tuple((fields.String(), fields.String(), fields.Boolean()))) #TODO color will bs hsl (tuple of 3) + set the default value
    SOGO_U_EVENT_DEFAULT_CLASS = fields.String(load_default="PUBLIC", dump_default="PUBLIC", validate=validate.OneOf(('PUBLIC', 'CONFIDENTIAL', 'PRIVATE')))
    SOGO_U_TASK_DEFAULT_CLASS = fields.String(load_default="PUBLIC", dump_default="PUBLIC", validate=validate.OneOf(('PUBLIC', 'CONFIDENTIAL', 'PRIVATE')))
    SOGO_U_EVENT_DEFAULT_REMINDER = fields.String() #TODO was fixed choices of values in SOGO in icalendar format like '-PT5M' or '-PT1W'
    SOGO_U_TASK_DEFAULT_REMINDER = fields.String() #TODO same as above

    #Contacts
    SOGO_U_COLLECT_UNKNWON_ADDRESSES = fields.Boolean(load_default=False, dump_default=False) #Collect address send to unknwon mail. (So next time it will be in autocompletion)
    SOGO_U_COLLECT_UNKNWON_ADDRESSEBOOK_NAME = fields.String(load_default="Collected", dump_default="Collected") #Name of the collected addressbook if SOGO_U_COLLECT_UNKNWON_ADDRESSES=True
    SOGO_U_CONTACT_CATEGORIES = fields.List(fields.Tuple((fields.String(), fields.Boolean()))) #Contact categories tuple (name, can_be_translated)
    #Work hours - not used for calendar view, but used for other functionnalities (like don't disturb me oustide work hours)
    SOGO_U_WORKDAY_START_TIME = fields.Time(format="%H:%M", load_default="08:00", dump_default="08:00")
    SOGO_U_WORKDAY_END_TIME = fields.Time(format="%H:%M", load_default="17:00", dump_default="17:00")
    SOGO_U_BUSY_OFF_HOURS = fields.Boolean(load_default=False, dump_default=False) #Show the user as busy outside the working hour