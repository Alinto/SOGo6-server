from __future__ import annotations  # pylint: disable=duplicate-code

from typing import TYPE_CHECKING

from flask import g, request
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.contact.InterfaceApiContactContact import InterfaceApiContactContact
from app.module.contact.ContactConst import IMPORT_MAX_BYTES
from app.module.contact.source.ContactSourceDb import LIST_SORTABLE_COLUMNS, SORTABLE_COLUMNS
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.api.paginate_sort_filter import collection_paginate, CustomPaginateResponse
from app.utils.errors import ERROR_CONTACT_IMPORT_NO_FILE, ERROR_CONTACT_IMPORT_TOO_LARGE
from app.utils.logger.logger import logger_api
from .schemas.addressbook import (
    AddressBookCreateSchema,
    AddressBookUpdateSchema,
    AddressBookListResponseSchema,
    AddressBookResponseSchema,
    ContactImportQueryArgsSchema,
    ContactImportResponseSchema,
    ContactImportUploadSchema,
)
from .schemas.contact import (
    ContactCreateSchema,
    ContactPatchSchema,
    ContactListResponseSchema,
    ContactResponseSchema,
    ContactSearchQueryArgsSchema,
    ContactAutocompleteQueryArgsSchema,
    ContactAutocompleteResponseSchema,
)
from .schemas.list import (
    ListCreateSchema,
    ListPatchSchema,
    ListCollectionResponseSchema,
    ListResponseSchema,
    ListSearchQueryArgsSchema,
)

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs

# collection_paginate types sort_value_set as a mutable set; SORTABLE_COLUMNS stays the immutable
# source of truth in the source layer and is exposed here as a plain set for the decorator.
_SORT_VALUES: set[str] = set(SORTABLE_COLUMNS)
_LIST_SORT_VALUES: set[str] = set(LIST_SORTABLE_COLUMNS)

# OpenAPI for the export routes: the serialization is content-negotiated from the Accept header, and the
# body is a vCard / LDIF document, not the usual JSON envelope - declared here so Swagger shows it.
_EXPORT_OPENAPI: dict = {
    "parameters": [{
        "in": "header", "name": "Accept", "required": False,
        "description": "Export serialization: 'text/vcard; version=3.0' (default, widest client support), "
                       "'text/vcard; version=4.0', 'text/ldif' or 'application/json'. An unsupported type returns 406.",
        "schema": {"type": "string", "enum": [
            "text/vcard; version=4.0", "text/vcard; version=3.0", "text/ldif", "application/json"]},
    }],
    "responses": {
        "200": {
            "description": "The serialized vCard / LDIF / JSON document, as a file attachment.",
            "content": {"text/vcard": {"schema": {"type": "string"}},
                        "text/ldif": {"schema": {"type": "string"}},
                        "application/json": {"schema": {"type": "object"}}},
        },
        "406": {"description": "The requested export format is not supported."},
    },
}

blp = Blueprint("Contact", __name__, url_prefix="")


@blp.before_request
def init_contact_config() -> None:  # pylint: disable=missing-function-docstring
    g.inter = InterfaceApiContactContact(
        process_setting=g.process_settings,
        user_domain_settings=g.user_domain_settings,
        user=g.user,
    )


@blp.route("/addressbooks")
class ApiAddressBookList(MethodView):
    """API to list and create address books."""

    @blp.response(200, AddressBookListResponseSchema)
    def get(self) -> ResponseReturnValue:
        """List all address books for the current user."""
        logger_api.debug("GET /addressbooks user=%s", g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.get_all_addressbooks()

    @blp.arguments(AddressBookCreateSchema)
    @blp.response(201, AddressBookResponseSchema)
    def post(self, body: dict) -> ResponseReturnValue:
        """Create a new address book."""
        logger_api.debug("POST /addressbooks user=%s body=%s", g.user.uid, body)
        interface: InterfaceApiContactContact = g.inter
        return interface.create_addressbook(body)


@blp.route("/addressbooks/<string:key>")
class ApiAddressBookDetail(MethodView):
    """API to retrieve, update and delete a single address book."""

    @blp.response(200, AddressBookResponseSchema)
    def get(self, key: str) -> ResponseReturnValue:
        """Get an address book by its key."""
        logger_api.debug("GET /addressbooks/%s user=%s", key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.get_addressbook(key)

    @blp.arguments(AddressBookUpdateSchema)
    @blp.response(200, AddressBookResponseSchema)
    def patch(self, body: dict, key: str) -> ResponseReturnValue:
        """Update an address book."""
        logger_api.debug("PATCH /addressbooks/%s user=%s body=%s", key, g.user.uid, body)
        interface: InterfaceApiContactContact = g.inter
        return interface.update_addressbook(key, body)

    @blp.response(200, AddressBookResponseSchema)
    def delete(self, key: str) -> ResponseReturnValue:
        """Delete an address book and all its contacts."""
        logger_api.debug("DELETE /addressbooks/%s user=%s", key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.delete_addressbook(key)


@blp.route("/addressbooks/<string:key>/contacts")
class ApiAddressBookContactList(MethodView):
    """API to list (paginated) and create contacts within one address book."""

    @blp.response(200, ContactListResponseSchema)
    @blp.arguments(ContactSearchQueryArgsSchema, location="query", arg_name="query_args")
    @collection_paginate(blp, sort_value_set=_SORT_VALUES, can_filter=False)
    def get(self, query_args: dict, collection_param: CollectionPaginateArgs, key: str) -> CustomPaginateResponse:
        """List the contacts of an address book, with search, sort and pagination."""
        logger_api.debug("GET /addressbooks/%s/contacts user=%s params=%s", key, g.user.uid, collection_param)
        interface: InterfaceApiContactContact = g.inter
        return interface.get_contacts(key, collection_param, search=query_args.get("search"))

    @blp.arguments(ContactCreateSchema)
    @blp.response(201, ContactResponseSchema)
    def post(self, body: dict, key: str) -> ResponseReturnValue:
        """Create a new contact in the address book."""
        logger_api.debug("POST /addressbooks/%s/contacts user=%s", key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.create_contact(key, body)


@blp.route("/contacts")
class ApiContactList(MethodView):
    """API to list (paginated) contacts across all the user's address books."""

    @blp.response(200, ContactListResponseSchema)
    @blp.arguments(ContactSearchQueryArgsSchema, location="query", arg_name="query_args")
    @collection_paginate(blp, sort_value_set=_SORT_VALUES, can_filter=False)
    def get(self, query_args: dict, collection_param: CollectionPaginateArgs) -> CustomPaginateResponse:
        """List contacts across every address book, with search, sort and pagination."""
        logger_api.debug("GET /contacts user=%s params=%s", g.user.uid, collection_param)
        interface: InterfaceApiContactContact = g.inter
        return interface.get_contacts(None, collection_param, search=query_args.get("search"))


@blp.route("/contacts/autocomplete")
class ApiContactAutocomplete(MethodView):
    """Recipient autocompletion: lightweight {name, email} suggestions across the user's contacts."""

    @blp.response(200, ContactAutocompleteResponseSchema)
    @blp.arguments(ContactAutocompleteQueryArgsSchema, location="query", arg_name="query_args")
    def get(self, query_args: dict) -> ResponseReturnValue:
        """Return recipient suggestions for the ``q`` query string."""
        logger_api.debug("GET /contacts/autocomplete user=%s q=%s", g.user.uid, query_args.get("q"))
        interface: InterfaceApiContactContact = g.inter
        return interface.autocomplete(query_args["q"])


@blp.route("/addressbooks/<string:key>/contacts/<string:contact_key>")
class ApiContactDetail(MethodView):
    """API to retrieve, update and delete a single contact within an address book."""

    @blp.response(200, ContactResponseSchema)
    def get(self, key: str, contact_key: str) -> ResponseReturnValue:
        """Get a contact by its key within the address book."""
        logger_api.debug("GET /addressbooks/%s/contacts/%s user=%s", key, contact_key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.get_contact(key, contact_key)

    @blp.arguments(ContactPatchSchema)
    @blp.response(200, ContactResponseSchema)
    def patch(self, body: dict, key: str, contact_key: str) -> ResponseReturnValue:
        """Apply partial updates to a contact."""
        logger_api.debug("PATCH /addressbooks/%s/contacts/%s user=%s", key, contact_key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.patch_contact(key, contact_key, body)

    @blp.response(200, ContactResponseSchema)
    def delete(self, key: str, contact_key: str) -> ResponseReturnValue:
        """Delete a contact."""
        logger_api.debug("DELETE /addressbooks/%s/contacts/%s user=%s", key, contact_key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.delete_contact(key, contact_key)


@blp.route("/addressbooks/<string:key>/lists")
class ApiListCollection(MethodView):
    """API to list (paginated) and create distribution lists within one address book."""

    @blp.response(200, ListCollectionResponseSchema)
    @blp.arguments(ListSearchQueryArgsSchema, location="query", arg_name="query_args")
    @collection_paginate(blp, sort_value_set=_LIST_SORT_VALUES, can_filter=False)
    def get(self, query_args: dict, collection_param: CollectionPaginateArgs, key: str) -> CustomPaginateResponse:
        """List the distribution lists of an address book, with search, sort and pagination."""
        logger_api.debug("GET /addressbooks/%s/lists user=%s params=%s", key, g.user.uid, collection_param)
        interface: InterfaceApiContactContact = g.inter
        return interface.get_lists(key, collection_param, search=query_args.get("search"))

    @blp.arguments(ListCreateSchema)
    @blp.response(201, ListResponseSchema)
    def post(self, body: dict, key: str) -> ResponseReturnValue:
        """Create a new distribution list in the address book."""
        logger_api.debug("POST /addressbooks/%s/lists user=%s", key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.create_list(key, body)


@blp.route("/addressbooks/<string:key>/lists/<string:list_key>")
class ApiListDetail(MethodView):
    """API to retrieve, update and delete a single distribution list within an address book."""

    @blp.response(200, ListResponseSchema)
    def get(self, key: str, list_key: str) -> ResponseReturnValue:
        """Get a distribution list by its key within the address book."""
        logger_api.debug("GET /addressbooks/%s/lists/%s user=%s", key, list_key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.get_list(key, list_key)

    @blp.arguments(ListPatchSchema)
    @blp.response(200, ListResponseSchema)
    def patch(self, body: dict, key: str, list_key: str) -> ResponseReturnValue:
        """Apply partial updates to a distribution list."""
        logger_api.debug("PATCH /addressbooks/%s/lists/%s user=%s", key, list_key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.patch_list(key, list_key, body)

    @blp.response(200, ListResponseSchema)
    def delete(self, key: str, list_key: str) -> ResponseReturnValue:
        """Delete a distribution list."""
        logger_api.debug("DELETE /addressbooks/%s/lists/%s user=%s", key, list_key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.delete_list(key, list_key)


#
# Import (grouped together in Swagger, followed by the symmetric export block)
#
def _read_import_upload(files: dict) -> str | tuple[dict, int]:
    """Read and decode the uploaded import ``file`` part.

    Shared by the three import routes: returns the decoded document on success, or an error envelope
    tuple when no file is present or the payload exceeds IMPORT_MAX_BYTES (the caller forwards it).
    """
    upload: FileStorage | None = files.get("file")
    if upload is None:
        return create_api_base_response(None, ERROR_CONTACT_IMPORT_NO_FILE)
    raw: bytes = upload.stream.read()
    if len(raw) > IMPORT_MAX_BYTES:
        return create_api_base_response(None, ERROR_CONTACT_IMPORT_TOO_LARGE)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


@blp.route("/addressbooks/import")
class ApiAddressBookImport(MethodView):
    """API to import a document as a NEW address book (created server-side) holding its contacts and lists."""

    accepted_content_types: set[str] = {"multipart/form-data"}

    @blp.arguments(ContactImportUploadSchema, location="files")
    @blp.arguments(ContactImportQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(201, ContactImportResponseSchema)
    def post(self, files: dict, query_args: dict) -> ResponseReturnValue:
        """Create a new address book from the uploaded document (upsert by uid)."""
        logger_api.debug("POST /addressbooks/import user=%s format=%s", g.user.uid, query_args.get("format"))
        document = _read_import_upload(files)
        if not isinstance(document, str):
            return document
        interface: InterfaceApiContactContact = g.inter
        return interface.import_addressbook(document, query_args["format"])


@blp.route("/addressbooks/<string:key>/contacts/import")
class ApiContactImport(MethodView):
    """API to import contacts from a document into an existing address book (upsert by uid)."""

    accepted_content_types: set[str] = {"multipart/form-data"}

    @blp.arguments(ContactImportUploadSchema, location="files")
    @blp.arguments(ContactImportQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, ContactImportResponseSchema)
    def post(self, files: dict, query_args: dict, key: str) -> ResponseReturnValue:
        """Import the uploaded contacts into the address book."""
        logger_api.debug("POST /addressbooks/%s/contacts/import user=%s format=%s",
                         key, g.user.uid, query_args.get("format"))
        document = _read_import_upload(files)
        if not isinstance(document, str):
            return document
        interface: InterfaceApiContactContact = g.inter
        return interface.import_contact(key, document, query_args["format"])


@blp.route("/addressbooks/<string:key>/lists/import")
class ApiListImport(MethodView):
    """API to import distribution lists from a document into an existing address book (upsert by uid)."""

    accepted_content_types: set[str] = {"multipart/form-data"}

    @blp.arguments(ContactImportUploadSchema, location="files")
    @blp.arguments(ContactImportQueryArgsSchema, location="query", arg_name="query_args")
    @blp.response(200, ContactImportResponseSchema)
    def post(self, files: dict, query_args: dict, key: str) -> ResponseReturnValue:
        """Import the uploaded distribution lists into the address book."""
        logger_api.debug("POST /addressbooks/%s/lists/import user=%s format=%s",
                         key, g.user.uid, query_args.get("format"))
        document = _read_import_upload(files)
        if not isinstance(document, str):
            return document
        interface: InterfaceApiContactContact = g.inter
        return interface.import_list(key, document, query_args["format"])


#
# Export (mirrors the import block above)
#
@blp.route("/addressbooks/<string:key>/export")
class ApiAddressBookExport(MethodView):
    """API to export a whole address book (contacts and lists) as vCard, LDIF or JSON."""

    @blp.doc(**_EXPORT_OPENAPI)
    def get(self, key: str) -> ResponseReturnValue:
        """Download the address book; the serialization is negotiated from the Accept header."""
        logger_api.debug("GET /addressbooks/%s/export user=%s accept=%s",
                         key, g.user.uid, request.headers.get("Accept"))
        interface: InterfaceApiContactContact = g.inter
        return interface.export_addressbook(key, request.headers.get("Accept", ""))


@blp.route("/addressbooks/<string:key>/contacts/<string:contact_key>/export")
class ApiContactExport(MethodView):
    """API to export a single contact as vCard, LDIF or JSON."""

    @blp.doc(**_EXPORT_OPENAPI)
    def get(self, key: str, contact_key: str) -> ResponseReturnValue:
        """Download one contact; the serialization is negotiated from the Accept header."""
        logger_api.debug("GET /addressbooks/%s/contacts/%s/export user=%s",
                         key, contact_key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.export_contact(key, contact_key, request.headers.get("Accept", ""))


@blp.route("/addressbooks/<string:key>/lists/<string:list_key>/export")
class ApiListExport(MethodView):
    """API to export a single distribution list as a vCard group card, LDIF groupOfNames or JSON."""

    @blp.doc(**_EXPORT_OPENAPI)
    def get(self, key: str, list_key: str) -> ResponseReturnValue:
        """Download one list; the serialization is negotiated from the Accept header."""
        logger_api.debug("GET /addressbooks/%s/lists/%s/export user=%s", key, list_key, g.user.uid)
        interface: InterfaceApiContactContact = g.inter
        return interface.export_list(key, list_key, request.headers.get("Accept", ""))
