"""Constants of the DAV server.

Protocol invariants shared by the WSGI application and the handlers. Tunable knobs belong to the
settings, not here.
"""

# Mount point of every DAV resource. Clients reach it directly or through the well-known URIs below.
DAV_ROOT_PATH: str = "/dav/"

# Bootstrapping URIs redirected to the DAV root (RFC 6764 section 5).
WELL_KNOWN_CALDAV_PATH: str = "/.well-known/caldav"
WELL_KNOWN_CARDDAV_PATH: str = "/.well-known/carddav"

# Methods served by the DAV server, each one by its own handler. Listed in the Allow header; any other
# method is answered 405.
DAV_METHODS: frozenset[str] = frozenset({"OPTIONS"})

# Compliance classes announced in the DAV header of OPTIONS responses (RFC 4918 section 18).
DAV_COMPLIANCE_CLASSES: tuple[str, ...] = ("1",)
