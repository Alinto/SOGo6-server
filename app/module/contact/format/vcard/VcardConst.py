# vCard property and parameter names, version strings and conventions shared by the vCard
# serializers and deserializers (RFC 6350 for 4.0, RFC 2426 for 3.0).

VCARD_VERSION_3: str = "3.0"
VCARD_VERSION_4: str = "4.0"

# Maximum octets on a line before folding (RFC 6350 §3.2).
VCARD_FOLD_LIMIT: int = 75

# Structural
PROP_BEGIN: str = "BEGIN"
PROP_END: str = "END"
VALUE_VCARD: str = "VCARD"
PROP_VERSION: str = "VERSION"

# Identity / name
PROP_FN: str = "FN"
PROP_N: str = "N"
PROP_NICKNAME: str = "NICKNAME"
PROP_KIND: str = "KIND"
PROP_UID: str = "UID"
PROP_REV: str = "REV"

# Organization
PROP_ORG: str = "ORG"
PROP_TITLE: str = "TITLE"
PROP_ROLE: str = "ROLE"

# Communication (typed / multi-valued)
PROP_EMAIL: str = "EMAIL"
PROP_TEL: str = "TEL"
PROP_ADR: str = "ADR"
PROP_URL: str = "URL"
PROP_IMPP: str = "IMPP"

# Misc
PROP_CATEGORIES: str = "CATEGORIES"
PROP_NOTE: str = "NOTE"
PROP_BDAY: str = "BDAY"
PROP_ANNIVERSARY: str = "ANNIVERSARY"
PROP_X_ANNIVERSARY: str = "X-ANNIVERSARY"
PROP_GEO: str = "GEO"
PROP_KEY: str = "KEY"
PROP_SOUND: str = "SOUND"
PROP_TZ: str = "TZ"
PROP_PHOTO: str = "PHOTO"

# Parameters
PARAM_TYPE: str = "TYPE"
PARAM_PREF: str = "PREF"
PARAM_VALUE_PREF: str = "PREF"  # vCard 3.0 marks the preferred entry with TYPE=PREF

# Distribution lists: vCard 4.0 uses KIND:group + MEMBER; vCard 3.0 / Apple use X-ADDRESSBOOKSERVER-*
KIND_GROUP: str = "group"
PROP_MEMBER: str = "MEMBER"
PROP_X_ABS_KIND: str = "X-ADDRESSBOOKSERVER-KIND"
PROP_X_ABS_MEMBER: str = "X-ADDRESSBOOKSERVER-MEMBER"

# A 4.0 UID is preferably a URI; we strip/add this prefix at the boundary, store the bare value.
UID_URN_PREFIX: str = "urn:uuid:"
# A 4.0 TEL value is preferably a "tel:" URI; we strip it on read, store the bare number.
TEL_URI_PREFIX: str = "tel:"
# A 4.0 GEO value is a "geo:lat,lon" URI; vCard 3.0 writes "lat;lon".
GEO_URI_PREFIX: str = "geo:"
