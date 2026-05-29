from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailSend import InterfaceApiMailSend
from app.utils.logger.logger import logger_api
from app.api.v1.mail.schemas.mailbox import (
    SendMailSchema,
    SendMailQuerySchema,
    SendMailResponseSchema,
    SendMailSchema,
    SendMailQuerySchema,
    SendMailResponseSchema,
    SaveDraftSchema,
    SaveDraftResponseSchema,
    SaveDraftQuerySchema,
)

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User

blp = Blueprint("Mail Send", __name__, url_prefix="/mailboxes/<string:account_id>/mail")


@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.

    This reads IMAP server and port from g.default_domain_settings if present (domain settings),
    falling back to the previous defaults otherwise.
    """
    logger_api.debug("Calling before_request for ApiMailSend")
    process: ProcessSetting = g.process_settings
    user: User = g.user
    user_domain: dict = g.user_domain_settings

    interface_api = InterfaceApiMailSend(
        process_setting=process,
        user=user,
        user_domain=user_domain,
    )
    g.inter = interface_api


@blp.route("/send")
class ApiMailSendAccountSend(MethodView):
    """
    Action: Send Email
    """
    @blp.arguments(SendMailQuerySchema, location='query', as_kwargs=False, error_status_code=400)
    @blp.arguments(SendMailSchema, example=SendMailSchema.example(), error_status_code=400)
    @blp.response(200, SendMailResponseSchema)
    def post(self, query_args: dict, mail_data: dict, account_id: str) -> ResponseReturnValue:
        """
        Send an email from the specified mailbox account.
        account_id="0" uses the main account, otherwise uses the external account with the given hash.
        """
        logger_api.debug("Calling ApiMailSendAccountSend.post for account_id: %s", account_id)
        interface: InterfaceApiMailSend = g.inter
        draft_uid = query_args.get("uid")
        return interface.send_mail(account_id, mail_data, draft_uid)



@blp.route("/save")
class ApiMailSendAccountSaveDraft(MethodView):
    """
    Action: Save a mail as a draft in the account's Drafts folder.
    """

    @blp.arguments(SaveDraftQuerySchema, location="query")
    @blp.arguments(SaveDraftSchema, example=SaveDraftSchema.example(), error_status_code=400)
    @blp.response(200, SaveDraftResponseSchema, example=SaveDraftResponseSchema.example())
    def post(self, query_args: dict, mail_data: dict, account_id: str) -> ResponseReturnValue:
        """Save a mail as a draft.

        If the query parameter ``uid`` is provided and a draft with that UID already exists,
        the existing draft is replaced with the new content. If ``uid`` is absent or the
        draft is not found, a new draft is created.

        In all cases the response contains the full saved draft including its (new) uid.

        :param mail_data: Validated draft data from the request body.
        :type mail_data: dict
        :param query_args: Validated query parameters (uid).
        :type query_args: dict
        :param account_id: The account identifier ("0" for main account, hash for external).
        :type account_id: str
        :return: API response containing the saved draft.
        :rtype: ResponseReturnValue
        """
        uid: str | None = query_args.get("uid", None)
        logger_api.debug(
            "Calling ApiMailSendAccountSaveDraft.post for account_id: %s, uid: %s",
            account_id,
            uid,
        )
        interface: InterfaceApiMailSend = g.inter
        return interface.save_draft(account_id, mail_data, uid)
