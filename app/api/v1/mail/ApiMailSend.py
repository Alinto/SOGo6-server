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
    SendMailResponseSchema,
    SaveDraftSchema,
    SaveDraftResponseSchema,
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
    Action: Send Email (no tmp_draft key).
    """
    @blp.arguments(SendMailSchema, example=SendMailSchema.example(), error_status_code=400)
    @blp.response(200, SendMailResponseSchema)
    def post(self, mail_data: dict, account_id: str) -> ResponseReturnValue:
        """
        Send an email from the specified mailbox account.
        account_id="0" uses the main account, otherwise uses the external account with the given hash.
        """
        logger_api.debug("Calling ApiMailSendAccountSend.post for account_id: %s", account_id)
        interface: InterfaceApiMailSend = g.inter
        return interface.send_mail(account_id, mail_data, key=None)


@blp.route("/<string:key>/send")
class ApiMailSendAccountSendWithDraft(MethodView):
    """
    Action: Send Email from an existing tmp_draft (validates and deletes the tmp_draft after sending).
    """
    @blp.arguments(SendMailSchema, example=SendMailSchema.example(), error_status_code=400)
    @blp.response(200, SendMailResponseSchema)
    def post(self, mail_data: dict, account_id: str, key: str) -> ResponseReturnValue:
        """
        Send an email linked to an existing tmp_draft key.
        The tmp_draft entry is validated and deleted after a successful send.
        """
        logger_api.debug(
            "Calling ApiMailSendAccountSendWithDraft.post for account_id: %s, key: %s",
            account_id,
            key,
        )
        interface: InterfaceApiMailSend = g.inter
        return interface.send_mail(account_id, mail_data, key=key)



@blp.route("/save")
class ApiMailSendAccountCreateDraft(MethodView):
    """
    Action: Create a new tmp_draft and save as a draft in the account's Drafts folder.
    """

    @blp.arguments(SaveDraftSchema, example=SaveDraftSchema.example(), error_status_code=400)
    @blp.response(200, SaveDraftResponseSchema, example=SaveDraftResponseSchema.example())
    def post(self, mail_data: dict, account_id: str) -> ResponseReturnValue:
        """Create a new draft (no existing tmp_draft key).

        Returns the draft content and the newly created tmp_draft key.
        """
        logger_api.debug("Calling ApiMailSendAccountCreateDraft.post for account_id: %s", account_id)
        interface: InterfaceApiMailSend = g.inter
        return interface.save_draft(account_id, mail_data, key=None)


@blp.route("/<string:key>/save")
class ApiMailSendAccountUpdateDraft(MethodView):
    """
    Action: Update an existing tmp_draft and save as a draft in the account's Drafts folder.
    """

    @blp.arguments(SaveDraftSchema, example=SaveDraftSchema.example(), error_status_code=400)
    @blp.response(200, SaveDraftResponseSchema, example=SaveDraftResponseSchema.example())
    def put(self, mail_data: dict, account_id: str, key: str) -> ResponseReturnValue:
        """Update an existing draft identified by *key*.

        Returns the updated draft content and the tmp_draft key.
        """
        logger_api.debug(
            "Calling ApiMailSendAccountUpdateDraft.put for account_id: %s, key: %s",
            account_id,
            key,
        )
        interface: InterfaceApiMailSend = g.inter
        return interface.save_draft(account_id, mail_data, key=key)


@blp.route("/attachments")
class ApiMailSendAccountCreateAttachment(MethodView):
    """
    Action: Upload an attachment, creating a new tmp_draft entry.
    """
    accepted_content_types = {"multipart/form-data"}

    @blp.arguments(
        UploadAttachmentFileSchema,
        location="files",
        content_type="multipart/form-data",
    )
    @blp.response(200, UploadAttachmentResponseSchema, example=UploadAttachmentResponseSchema.example())
    def post(self, file: dict, account_id: str) -> ResponseReturnValue:
        """Upload an attachment, creating a new tmp_draft entry.

        The file must be sent as multipart/form-data with a field named 'file'.
        """
        logger_api.debug(
            "Calling ApiMailSendAccountCreateAttachment.post for account_id: %s",
            account_id,
        )

        file = request.files.get("file")
        if file is None:
            raise RequestException(err.ERROR_TMP_DRAFT_UPLOAD_NO_FILE.m, error=err.ERROR_TMP_DRAFT_UPLOAD_NO_FILE)

        filename: str = file.filename or "attachment"
        content_type: str = file.content_type or "application/octet-stream"
        file_data: bytes = file.read()

        interface: InterfaceApiMailSend = g.inter
        return interface.upload_attachment(account_id, filename, content_type, file_data, key=None)


@blp.route("/<string:key>/attachments")
class ApiMailSendAccountUploadAttachment(MethodView):
    """
    Action: Upload an attachment to an existing tmp_draft entry.
    """
    accepted_content_types = {"multipart/form-data"}

    @blp.arguments(
        UploadAttachmentFileSchema,
        location="files",
        content_type="multipart/form-data",
    )
    @blp.response(200, UploadAttachmentResponseSchema, example=UploadAttachmentResponseSchema.example())
    def post(self, file: dict, account_id: str, key: str) -> ResponseReturnValue:
        """Upload an attachment to the draft identified by *key*.

        The file must be sent as multipart/form-data with a field named 'file'.
        If the draft is currently locked, the request will wait up to 2 seconds before returning 409.
        """
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
        return interface.upload_attachment(account_id, filename, content_type, file_data, key=key)
