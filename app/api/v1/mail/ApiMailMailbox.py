from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailMailbox import InterfaceApiMailMailbox
from app.utils.logger.logger import logger_api
from app.utils.api.ApiBaseResponse import ApiBaseResponse
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
    MailboxBatchActionSchema,
    MailboxBatchActionResponseSchema,
)

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User

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


@blp.route("/<string:account_id>/batch-action")
class ApiMailBoxesAccountBatchAction(MethodView):
    """
    Resource: Batch actions across the whole mailbox
    """
    @blp.arguments(MailboxBatchActionSchema, example=MailboxBatchActionSchema.example(), error_status_code=400)
    @blp.response(200, MailboxBatchActionResponseSchema, example=MailboxBatchActionResponseSchema.example())
    def post(self, data: dict, account_id: str) -> ResponseReturnValue:
        """Perform an action (tag, untag, move, spam, ham, copy) on mails from several folders of the account at once.

        Behaves like the per-folder batch action endpoint, except that ``uids`` maps folder names
        to their list of mail UIDs, so mails from multiple folders can be processed in a single call.
        Each folder is processed independently: a failure on one folder does not prevent the others
        from being processed, and the per-folder outcome is reported in the response's ``results``
        and ``errors`` fields.

        **Supported actions:**

        * **tag**: Add one or more tags to the selected mails. Tags are provided in the ``data`` field as a list of strings.
        * **untag**: Remove one or more tags from the selected mails. Tags to remove are provided in the ``data`` field as a list of strings.
        * **move**: Move the selected mails to another folder. The destination folder name must be provided in the ``data`` field as a string.
        * **spam**: Mark the selected mails as spam.
        * **ham**: Mark the selected mails as not spam.
        * **copy**: Copy the selected mails to another folder. The destination folder name must be provided in the ``data`` field as a string.
        * **delete**: Delete the selected mails, following the user's mail delete behavior preference.
        * **illegal**: Report the selected mails as illegal content and move them to the Junk folder.
        * **phishing**: Report the selected mails as phishing and move them to the Junk folder.

        :param data: The batch action data containing 'uids' (folder name -> list of uids), 'action' and optional 'data' field
        :type data: dict
        :param account_id: The account identifier
        :type account_id: str
        :return: A response indicating the per-folder result of the action
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailBoxesAccountBatchAction.post for account_id: %s, uids: %s with action: %s",
            account_id,
            data["uids"],
            data["action"]
        )
        interface: InterfaceApiMailMailbox = g.inter
        return interface.mailbox_batch_action(account_id, data)


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

