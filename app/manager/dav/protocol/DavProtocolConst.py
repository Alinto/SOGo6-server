"""Constants of the WebDAV, CalDAV and CardDAV protocols, shared by the DAV server and DAV clients.

Element and property names use the Clark notation of ElementTree: "{namespace}name".
"""

# XML namespaces (RFC 4918 section 21.2, RFC 4791 section 1.2, RFC 6352 section 2), plus the extensions of
# CalendarServer (getctag) and Apple (calendar color) that clients rely on.
NS_DAV: str = "DAV:"
NS_CALDAV: str = "urn:ietf:params:xml:ns:caldav"
NS_CARDDAV: str = "urn:ietf:params:xml:ns:carddav"
NS_CALENDARSERVER: str = "http://calendarserver.org/ns/"
NS_APPLE_ICAL: str = "http://apple.com/ns/ical/"

# Prefixes of the namespaces in the responses. Clients log the responses: fixed prefixes keep these logs
# readable, where ElementTree would number them (ns0, ns1...).
NS_PREFIXES: dict[str, str] = {
    "D": NS_DAV,
    "C": NS_CALDAV,
    "CR": NS_CARDDAV,
    "CS": NS_CALENDARSERVER,
    "IC": NS_APPLE_ICAL,
}

# Elements of a PROPFIND request (RFC 4918 section 14).
DAV_PROPFIND: str = "{DAV:}propfind"
DAV_ALLPROP: str = "{DAV:}allprop"
DAV_PROPNAME: str = "{DAV:}propname"
DAV_PROP: str = "{DAV:}prop"
DAV_INCLUDE: str = "{DAV:}include"

# Elements of a multistatus response (RFC 4918 section 14).
DAV_MULTISTATUS: str = "{DAV:}multistatus"
DAV_RESPONSE: str = "{DAV:}response"
DAV_HREF: str = "{DAV:}href"
DAV_PROPSTAT: str = "{DAV:}propstat"
DAV_STATUS: str = "{DAV:}status"

# Properties locating the account of the user (RFC 4918 section 15, RFC 5397 section 3, RFC 3744 section 4,
# RFC 4791 section 6.2.1, RFC 6638 section 2.4.1, RFC 6352 section 7.1.1).
DAV_RESOURCETYPE: str = "{DAV:}resourcetype"
DAV_DISPLAYNAME: str = "{DAV:}displayname"
DAV_CURRENT_USER_PRINCIPAL: str = "{DAV:}current-user-principal"
DAV_PRINCIPAL_URL: str = "{DAV:}principal-URL"
DAV_ALTERNATE_URI_SET: str = "{DAV:}alternate-URI-set"
DAV_GROUP_MEMBERSHIP: str = "{DAV:}group-membership"
CALDAV_CALENDAR_HOME_SET: str = "{urn:ietf:params:xml:ns:caldav}calendar-home-set"
CALDAV_CALENDAR_USER_ADDRESS_SET: str = "{urn:ietf:params:xml:ns:caldav}calendar-user-address-set"
CARDDAV_ADDRESSBOOK_HOME_SET: str = "{urn:ietf:params:xml:ns:carddav}addressbook-home-set"

# Properties defined by WebDAV (RFC 4918 section 15), the only live properties an allprop returns (RFC 4918
# section 9.1): the specifications of the other ones ask not to return them (RFC 3744, RFC 4791, RFC 6352,
# RFC 6638) or leave it to the server (RFC 5397).
DAV_ALLPROP_PROPERTIES: frozenset[str] = frozenset(
    {
        "{DAV:}creationdate",
        DAV_DISPLAYNAME,
        "{DAV:}getcontentlanguage",
        "{DAV:}getcontentlength",
        "{DAV:}getcontenttype",
        "{DAV:}getetag",
        "{DAV:}getlastmodified",
        "{DAV:}lockdiscovery",
        DAV_RESOURCETYPE,
        "{DAV:}supportedlock",
    }
)

# Properties of a calendar collection (RFC 4791 section 5.2), plus the change tag of CalendarServer and the color
# of Apple.
CALDAV_CALENDAR_DESCRIPTION: str = "{urn:ietf:params:xml:ns:caldav}calendar-description"
CALDAV_CALENDAR_TIMEZONE: str = "{urn:ietf:params:xml:ns:caldav}calendar-timezone"
CALDAV_SUPPORTED_CALENDAR_COMPONENT_SET: str = "{urn:ietf:params:xml:ns:caldav}supported-calendar-component-set"
CALDAV_COMP: str = "{urn:ietf:params:xml:ns:caldav}comp"
CALENDARSERVER_GETCTAG: str = "{http://calendarserver.org/ns/}getctag"
APPLE_ICAL_CALENDAR_COLOR: str = "{http://apple.com/ns/ical/}calendar-color"

# Privileges of a resource (RFC 3744 sections 3, 5.3 and 5.4, RFC 4791 section 6.1).
DAV_SUPPORTED_PRIVILEGE_SET: str = "{DAV:}supported-privilege-set"
DAV_SUPPORTED_PRIVILEGE: str = "{DAV:}supported-privilege"
DAV_CURRENT_USER_PRIVILEGE_SET: str = "{DAV:}current-user-privilege-set"
DAV_PRIVILEGE: str = "{DAV:}privilege"
DAV_ABSTRACT: str = "{DAV:}abstract"
DAV_DESCRIPTION: str = "{DAV:}description"
DAV_READ: str = "{DAV:}read"
CALDAV_READ_FREE_BUSY: str = "{urn:ietf:params:xml:ns:caldav}read-free-busy"

# Language attribute of the descriptions (XML 1.0 section 2.12).
XML_LANG: str = "{http://www.w3.org/XML/1998/namespace}lang"

# RFC 3744 section 5.3 requires the language of every privilege description (xml:lang). The descriptions are
# written in the code, in English, and not translated after Accept-Language: one language for all of them.
DAV_DESCRIPTION_LANGUAGE: str = "en"

# Resource types (RFC 4918 section 14.3, RFC 3744 section 4, RFC 4791 section 4.2).
DAV_COLLECTION: str = "{DAV:}collection"
DAV_PRINCIPAL: str = "{DAV:}principal"
CALDAV_CALENDAR: str = "{urn:ietf:params:xml:ns:caldav}calendar"

# Body of an error response and the conditions it names (RFC 4918 sections 14.5 and 16).
DAV_ERROR: str = "{DAV:}error"
DAV_PROPFIND_FINITE_DEPTH: str = "{DAV:}propfind-finite-depth"
