# LDIF attribute names, object classes and the directory mapping shared by the LDIF serializers
# and deserializers (RFC 2849 for the format, RFC 4519 / inetOrgPerson for the schema).

# Octets on a line before folding, continuation lines starting with a space (RFC 2849).
LDIF_FOLD_LIMIT: int = 76

ATTR_DN: str = "dn"
ATTR_OBJECTCLASS: str = "objectClass"

# Object classes
OC_TOP: str = "top"
OC_PERSON: str = "person"
OC_ORGANIZATIONAL_PERSON: str = "organizationalPerson"
OC_INETORGPERSON: str = "inetOrgPerson"
OC_GROUPOFNAMES: str = "groupOfNames"

# inetOrgPerson attributes used to carry a CardContact
ATTR_CN: str = "cn"
ATTR_SN: str = "sn"
ATTR_GIVENNAME: str = "givenName"
ATTR_DISPLAYNAME: str = "displayName"
ATTR_MAIL: str = "mail"
ATTR_TELEPHONE: str = "telephoneNumber"
ATTR_MOBILE: str = "mobile"
ATTR_O: str = "o"
ATTR_OU: str = "ou"
ATTR_TITLE: str = "title"
ATTR_DESCRIPTION: str = "description"
ATTR_STREET: str = "street"
ATTR_L: str = "l"
ATTR_ST: str = "st"
ATTR_POSTALCODE: str = "postalCode"
ATTR_C: str = "c"
ATTR_UID: str = "uid"
ATTR_JPEGPHOTO: str = "jpegPhoto"

# inetOrgPerson stores a photo as the binary jpegPhoto attribute. Its real type is sniffed from the
# bytes on read (the name is nominal: PNG/GIF are common too); this is the fallback when unrecognised.
JPEGPHOTO_MEDIA_TYPE: str = "image/jpeg"

# groupOfNames
ATTR_MEMBER: str = "member"

# Base DN used to build / recognise the relative distinguished name of an exported entry.
BASE_DN: str = "ou=contacts"

# The phone TYPE that maps to the "mobile" attribute rather than telephoneNumber.
MOBILE_TYPE: str = "cell"

LDIF_VERSION_HEADER: str = "version: 1"
