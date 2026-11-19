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

# Resource types (RFC 4918 section 14.3, RFC 3744 section 4).
DAV_COLLECTION: str = "{DAV:}collection"
DAV_PRINCIPAL: str = "{DAV:}principal"
