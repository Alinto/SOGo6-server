from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailMailbox import InterfaceApiMailMailbox
from app.utils.logger.logger import logger_api
from app.utils.api.ApiBaseResponse import ApiBaseResponse
from app.utils.api.paginate_sort_filter import collection_paginate, CustomPaginateResponse
from app.api.v1.mail.schemas.mailbox import (
    MailboxCreateSchema,
    MailboxUpdateSchema,
    MailboxResponseSchema,
    MailboxListResponseSchema,
    DelegationCreateSchema,
    DelegationListResponseSchema,
    DelegationResponseSchema,
    MailboxPurgeSchema,
    MailboxPurgeResponseSchema,
    MailboxSearchSchema,
    MailboxSearchResponseSchema,
)

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs

blp = Blueprint("Mail Account", __name__, url_prefix="/mailboxes")


@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.

    This reads IMAP server and port from g.default_domain_settings if present (domain settings),
    falling back to the previous defaults otherwise.
    """
    logger_api.debug("Calling before_request for ApiMailAccount")
    process: ProcessSetting = g.process_settings
    user: User = g.user
    user_domain: dict = g.user_domain_settings

    interface_api = InterfaceApiMailMailbox(
        process_setting=process,
        user=user,
        user_domain=user_domain,
    )
    g.inter = interface_api


@blp.route("")
class ApiMailBoxes(MethodView):
    """
    API to manage mailboxes.
    """
    @blp.response(200, MailboxListResponseSchema)
    def get(self) -> ResponseReturnValue:
        """
        List all configured mailboxes (0 = main account, others = external accounts)
        """
        logger_api.debug("Calling ApiMailBoxes.get to list all mailboxes")
        interface: InterfaceApiMailMailbox = g.inter
        return interface.list_mailboxes()

    @blp.arguments(MailboxCreateSchema, example=MailboxCreateSchema.example(), error_status_code=400)
    @blp.response(201, MailboxResponseSchema)
    def post(self, mailbox_data: dict) -> ResponseReturnValue:
        """
        Create a new mailbox (add external account)
        """
        logger_api.debug("Calling ApiMailBoxes.post to create a new mailbox with data: %s", mailbox_data)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.create_mailbox(mailbox_data)

@blp.route("/<string:account_id>")
class ApiMailBoxesAccount(MethodView):
    """
    Resource: Mailbox by hash
    """
    @blp.response(200, MailboxResponseSchema)
    def get(self, account_id: str) -> ResponseReturnValue:
        """
        Get a specific account by its hash.
        If account_id is "0", returns the main account.
        Otherwise, returns the external account with the given hash.
        """
        logger_api.debug("Calling ApiMailBoxesAccount.get for account_id: %s", account_id)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.get_mailbox(account_id)

    @blp.arguments(MailboxUpdateSchema, example=MailboxUpdateSchema.example(), error_status_code=400)
    @blp.response(200, MailboxResponseSchema)
    def patch(self, mailbox_data: dict, account_id: str) -> ResponseReturnValue:
        """
        Update mailbox settings
        If account_id is "0", updates the main account
        Otherwise, updates the external account with the given hash
        """
        logger_api.debug("Calling ApiMailBoxesAccount.patch for account_id: %s with data: %s", account_id, mailbox_data)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.update_mailbox(account_id, mailbox_data)

    @blp.response(204, ApiBaseResponse)
    def delete(self, account_id: str) -> ResponseReturnValue:
        """
        Delete a mailbox (only external accounts)
        """
        logger_api.debug("Calling ApiMailBoxesAccount.delete for account_id: %s", account_id)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.delete_mailbox(account_id)



@blp.route("/<string:account_id>/delegate")
class ApiMailBoxesAccountDelegates(MethodView):
    """
    Action: Mailbox Delegations
    """
    @blp.response(200, DelegationListResponseSchema)
    def get(self, account_id: str) -> ResponseReturnValue:
        """
        Get delegates for this mailbox
        
        Note: Currently only supported for main account (account_id="0")
        """
        logger_api.debug("Calling ApiMailBoxesAccountDelegates.get for account_id: %s", account_id)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.get_mailbox_delegates(account_id)

    @blp.arguments(DelegationCreateSchema, example=DelegationCreateSchema.example(), error_status_code=400)
    @blp.response(201, DelegationResponseSchema)
    def post(self, data: dict, account_id: str) -> ResponseReturnValue:
        """
        Create a new delegate for this mailbox
        
        Note: Currently only supported for main account (account_id="0")
        """
        logger_api.debug("Calling ApiMailBoxesAccountDelegates.post for account_id: %s with data: %s", account_id, data)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.create_mailbox_delegate(account_id, data)


@blp.route("/<string:account_id>/purge")
class ApiMailBoxesAccountPurge(MethodView):
    """
    Resource: Purge Mailbox
    """
    @blp.arguments(MailboxPurgeSchema, example=MailboxPurgeSchema.example(), error_status_code=400)
    @blp.response(200, MailboxPurgeResponseSchema, example=MailboxPurgeResponseSchema.example())
    def post(self, purge_data: dict, account_id: str) -> ResponseReturnValue:
        """
        Action: purge all folders from the specified mailbox
        """
        logger_api.debug("Calling ApiMailBoxesAccountPurge.post for account_id: %s with data: %s", account_id, purge_data)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.purge_mailbox(account_id, purge_data)


@blp.route("/<string:account_id>/search")
class ApiMailBoxesAccountSearch(MethodView):
    """
    Resource: Advanced Mail Search
    """
    @blp.arguments(MailboxSearchSchema, example=MailboxSearchSchema.example(), error_status_code=400)
    @blp.response(200, MailboxSearchResponseSchema)
    @collection_paginate(blp, can_sort=True, sort_value_set={"date", "relevance", "sender", "subject", "size"},
                         can_filter=True, filter_value_set={"contents", "deleted"})
    def post(self, search_params: dict, collection_param: "CollectionPaginateArgs", account_id: str) -> CustomPaginateResponse:
        """
        Advanced mail search across one or multiple folders.

        * **operator**: str, 'AND' (default) or 'OR' - how the criteria below are combined.
          With 'AND' every provided criterion must match, with 'OR' at least one must match.
        * **text**: str, full text search in subject/sender/recipients/body
        * **folders**: list[str], list of folder paths to search in (e.g. ["INBOX", "Sent"] or ["all"] for all folders)
        * **include_subfolders**: bool, default True - when True, also search the subfolders of each folder listed in "folders"; when False, search only the exact folders listed. Ignored when "folders" is empty or ["all"].
        * **date_range**: dict, date range for the search (e.g. {"from": "2023-01-01", "to": "2023-01-31"})
        * **has_attachments**: bool, whether to search for emails with attachments
        * **to**: str, email address to search for in either the recipient (To) or copy (Cc) headers
        * **bcc**: str, blind copy (Bcc) email address to search for
        * **from**: list[str], list of sender email addresses to search for
        * **subject** : str, keywords to search for in the email subject
        * **attachment_type**: list[str], list of attachment types to search for (e.g. ["pdf", "jpg"])
        * **is_read**: bool, whether to search for read or unread emails
        * **labels**: list[str], list of labels/tags to search for

        All search criteria are optional and combined using the "operator" field (AND by default, OR to match any criterion).
        Pagination, sorting and field filtering are controlled via query parameters (page, page_size, sort_by, sort_order, fields, fields_action).
        """
        logger_api.debug("Calling ApiMailBoxesAccountSearch.post for account_id: %s with params: %s", account_id, search_params)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.search_mailbox(account_id, search_params, collection_param)
