from .format.vcard.VcardConst import VCARD_VERSION_4

# Default vCard VERSION (RFC 6350 §6.7.9) applied when a contact does not carry one.
DEFAULT_VCARD_VERSION: str = VCARD_VERSION_4

# Fallback formatted name (vCard FN) used when a contact has neither a structured name,
# an organization nor a nickname to derive a display name from.
DEFAULT_DISPLAY_NAME: str = "Unnamed Contact"

# Name given to the personal address book provisioned for a user at first login.
DEFAULT_ADDRESSBOOK_NAME: str = "Personal contacts"

# Maximum number of contacts scanned for a recipient autocompletion query on the local books.
AUTOCOMPLETE_DEFAULT_LIMIT: int = 25

# Maximum size of an inline file embedded in a contact (e.g. a photo), in kilobytes. The file layer
# rejects a larger inline payload when saved, before it is offloaded to storage.
FILE_MAX_SIZE_KB: int = 2048

# Maximum size of an uploaded address book import document (vCard / LDIF), in bytes. The whole request
# is also capped at the WSGI layer; this bounds the in-memory parse of one import.
IMPORT_MAX_BYTES: int = 10 * 1024 * 1024

# Display-name prefix for the address book created by a whole-book import (no name in the document).
IMPORT_BOOK_NAME_PREFIX: str = "Import"

# Media types accepted for an inline contact file. The real type is sniffed from the bytes by the
# file layer, so a payload whose content is not one of these is rejected when saved. SVG is
# intentionally excluded: it is a script-bearing document and a stored-XSS vector when a client
# renders the file as anything other than an <img> source.
ALLOWED_FILE_MIME_TYPES: frozenset[str] = frozenset({
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff",
})
