"""Constants of the DAV server.

Protocol invariants shared by the WSGI application and the handlers. Tunable knobs belong to the
settings, not here.
"""

# Mount point of every DAV resource. Clients reach it directly or through the well-known URIs below.
DAV_ROOT_PATH: str = "/dav/"

# Bootstrapping URIs redirected to the DAV root (RFC 6764 section 5).
WELL_KNOWN_CALDAV_PATH: str = "/.well-known/caldav"
WELL_KNOWN_CARDDAV_PATH: str = "/.well-known/carddav"

# Names of the homes of the calendars and of the address books, under the principal of a user.
DAV_CALENDAR_HOME: str = "Calendar"
DAV_ADDRESSBOOK_HOME: str = "Contacts"

# Methods served by the DAV server, each one by its own handler. Listed in the Allow header; any other
# method is answered 405.
DAV_METHODS: frozenset[str] = frozenset({"OPTIONS", "PROPFIND"})

# Content-Type of the XML bodies: multistatus and error responses.
DAV_XML_CONTENT_TYPE: str = "application/xml; charset=utf-8"

# Compliance classes announced in the DAV header of OPTIONS responses (RFC 4918 section 18).
DAV_COMPLIANCE_CLASSES: tuple[str, ...] = ("1",)

# Protection space announced in the Basic challenge (RFC 7617 section 2).
DAV_AUTH_REALM: str = "SOGo"

# WWW-Authenticate value of every 401, credentials expected in UTF-8 (RFC 7617 section 2.1).
DAV_AUTH_CHALLENGE: str = f'Basic realm="{DAV_AUTH_REALM}", charset="UTF-8"'

# Characters of LDAP filters and DNs (RFC 4515 section 3, RFC 4514 section 2.4), refused in a login: the
# login is inserted in both, and a wildcard would match another account. A leading "#" is refused as well, a
# DN value starting with it is read as hexadecimal BER. "+" is kept on purpose for mail subaddresses,
# although it separates the values of a DN. "/" is refused too: the login is a segment of the path of the
# principal of the user.
DAV_LOGIN_FORBIDDEN_CHARS: frozenset[str] = frozenset('*()\\,=;<>"/')

# Separator of the login "<login>!<alias>" of an account alias. macOS Contacts syncs a single address book per
# account and tells its accounts apart by login: the user adds one account per address book, the alias being
# the key of the address book. A login cannot contain it.
DAV_ACCOUNT_ALIAS_SEPARATOR: str = "!"

# Cache keys of the wrong passwords of a login and of a blocked login, the login is appended.
DAV_LOGIN_FAILURE_PREFIX: str = "dav_login_failure:"
DAV_LOGIN_BLOCKED_PREFIX: str = "dav_login_blocked:"
