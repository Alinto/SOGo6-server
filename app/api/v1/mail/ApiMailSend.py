from typing import TYPE_CHECKING

from flask import g, request
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailSend import InterfaceApiMailSend
from app.utils.logger.logger import logger_api
from app.utils.exceptions import RequestException
from app.utils import errors as err

from app.api.v1.mail.schemas.send import (
    SendMailSchema,
    SendMailQuerySchema,
    SendMailResponseSchema,
    SaveDraftSchema,
    SaveDraftResponseSchema,
    SaveDraftQuerySchema,
    UploadAttachmentQuerySchema,
    UploadAttachmentResponseSchema,
    UploadAttachmentFileSchema,
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
        key = query_args.get("key")
        return interface.send_mail(account_id, mail_data, key)



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
        """
        key: str | None = query_args.get("key", None)
        logger_api.debug(
            "Calling ApiMailSendAccountSaveDraft.post for account_id: %s, key: %s",
            account_id,
            key,
        )
        interface: InterfaceApiMailSend = g.inter
        return interface.save_draft(account_id, mail_data, key)


@blp.route("/upload")
class ApiMailSendAccountUploadAttachment(MethodView):
    """
    Action: Upload an attachment to a mail in progress (draft).
    """
    accepted_content_types = {"multipart/form-data"}
    @blp.arguments(UploadAttachmentQuerySchema, location="query")
    @blp.arguments(
        UploadAttachmentFileSchema,
        location="files",
        content_type="multipart/form-data",
    )
    @blp.response(200, UploadAttachmentResponseSchema, example=UploadAttachmentResponseSchema.example())
    def post(self, query_args: dict, file: dict, account_id: str) -> ResponseReturnValue:
        """Upload an attachment to the mail in progress.

        The file must be sent as multipart/form-data with a field named 'file'.
        If no key is provided, a new tmp_draft entry is created.
        If the draft is currently locked, the request will wait up to 2 seconds before returning 409.
        """
        key: str | None = query_args.get("key", None)
        logger_api.debug(
            "Calling ApiMailSendAccountUploadAttachment.post for account_id: %s, key: %s",
            account_id,
            key,
        )

        file = request.files.get("file")
        if file is None:
            raise RequestException(err.ERROR_TMP_DRAFT_UPLOAD_NO_FILE.m, error=err.ERROR_TMP_DRAFT_UPLOAD_NO_FILE)

        filename: str = file.filename or "attachment"
        content_type: str = file.content_type or "application/octet-stream"
        file_data: bytes = file.read()

        interface: InterfaceApiMailSend = g.inter
        return interface.upload_attachment(account_id, filename, content_type, file_data, key)
