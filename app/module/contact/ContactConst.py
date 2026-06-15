# Default vCard VERSION (RFC 6350 §6.7.9) applied when a contact does not carry one.
DEFAULT_VCARD_VERSION: str = "4.0"

# Fallback formatted name (vCard FN) used when a contact has neither a structured name,
# an organization nor a nickname to derive a display name from.
DEFAULT_DISPLAY_NAME: str = "Unnamed Contact"

# Name given to the personal address book provisioned for a user at first login.
DEFAULT_ADDRESSBOOK_NAME: str = "Personal contacts"

# Maximum number of contacts scanned for a recipient autocompletion query on the local books.
# The external directory applies its own US_AUTO_QUERY_LIMIT once ContactSourceDirectory is wired.
AUTOCOMPLETE_DEFAULT_LIMIT: int = 25
