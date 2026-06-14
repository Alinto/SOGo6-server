from __future__ import annotations  # pylint: disable=duplicate-code

from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.contact.InterfaceApiContactContact import InterfaceApiContactContact
from app.module.contact.source.ContactSourceDb import SORTABLE_COLUMNS
from app.utils.api.paginate_sort_filter import collection_paginate, CustomPaginateResponse
from app.utils.logger.logger import logger_api
from .schemas.addressbook import (
    AddressBookCreateSchema,
    AddressBookUpdateSchema,
    AddressBookListResponseSchema,
    AddressBookResponseSchema,
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

if TYPE_CHECKING:
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs

# collection_paginate types sort_value_set as a mutable set; SORTABLE_COLUMNS stays the immutable
# source of truth in the source layer and is exposed here as a plain set for the decorator.
_SORT_VALUES: set[str] = set(SORTABLE_COLUMNS)

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
