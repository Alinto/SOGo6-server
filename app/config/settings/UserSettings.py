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

    #Contacts
    SOGO_U_COLLECT_UNKNWON_ADDRESSES = fields.Boolean(load_default=False, dump_default=False) #Collect address send to unknwon mail. (So next time it will be in autocompletion)
    SOGO_U_COLLECT_UNKNWON_ADDRESSEBOOK_NAME = fields.String(load_default="Collected", dump_default="Collected") #Name of the collected addressbook if SOGO_U_COLLECT_UNKNWON_ADDRESSES=True
    
    #Work hours - not used for calendar view, but used for other functionnalities (like don't disturb me oustide work hours)
    SOGO_U_WORKDAY_START_TIME = fields.Time(format="%H:%M", load_default="08:00", dump_default="08:00")
    SOGO_U_WORKDAY_END_TIME = fields.Time(format="%H:%M", load_default="17:00", dump_default="17:00")