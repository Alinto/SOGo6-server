"""
iCalendar RFC 5545 constants shared between the serializer and deserializer.
"""

# Product identifier emitted in PRODID property
PRODID = "-//SOGo//CalCalendarSerializer//EN"

# iCalendar standard version
ICAL_VERSION = "2.0"

# Calendar scale (only GREGORIAN is supported)
CALSCALE = "GREGORIAN"

# Component names - used to identify components during parsing
COMP_VCALENDAR = "VCALENDAR"
COMP_VEVENT = "VEVENT"
COMP_VTIMEZONE = "VTIMEZONE"
COMP_VALARM = "VALARM"
COMP_VTODO = "VTODO"
COMP_VJOURNAL = "VJOURNAL"
COMP_VFREEBUSY = "VFREEBUSY"
