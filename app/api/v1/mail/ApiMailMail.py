from __future__ import annotations
from typing import TYPE_CHECKING

from io import BytesIO

from flask import g, send_file
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailMail import InterfaceApiMailMail
from app.utils.logger.logger import logger_api
from app.utils.api.paginate_sort_filter import collection_paginate, CustomPaginateResponse
from .schemas.mail import (
    MailDetailResponseSchema,
    MailListResponseSchema,
    MailDeleteResponseSchema,
    MailRawResponseSchema,
    MailActionSchema,
    MailDownloadSchema,
    MailEditResponseSchema,
    MailReplyResponseSchema,
)

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs

blp = Blueprint("Mail", __name__, url_prefix="/mailboxes/<string:account_id>/folders/<path:folder_name>/mails")


@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.

    Provide user_conf as either a single dict or a list of dicts (accounts).
    Example below provides two accounts (primary index 0, secondary index 1).
    """
    logger_api.debug("Calling before_request for ApiMailDetail")
    process: ProcessSetting = g.process_settings
    user_domain_settings: dict = g.user_domain_settings
    user: User = g.user

    interface_api = InterfaceApiMailMail(
        process_setting=process,
        user_domain_settings=user_domain_settings,
        user=user
    )
    g.inter = interface_api


@blp.route("")
class ApiMailFolderIdMail(MethodView):
    """
    API to list mails in a specific mail folder
    """

    @blp.response(200, MailListResponseSchema, example=MailListResponseSchema.example())
    @collection_paginate(blp, sort_value_set=MailListResponseSchema.sort_by_values(), filter_value_set=MailListResponseSchema.filter_by_values())
    def get(self, collection_param: CollectionPaginateArgs, account_id: str, folder_name: str) -> CustomPaginateResponse:
        """Fetch the list of mails in a specific folder.

        The filtering for this endpoint is special:\r\n
        By default, the content of the mail is returned. But this is heavy load both for the api request and
        the mail server (imap) request.\r\n
        Without content you will have:

        * **uid**: str, Unique identifier of the mail. Use with others mails endpoint,
        * **size**: int, size in kb of the mail
        * **deleted**: bool, the mail is flag as deleted
        * **seen**: bool, if the mail has already been seen
        * **flagged**: bool, the mail is flag as important
        * **answered**: bool, the mail has been answered
        * **forwarded**: bool, the mail has been forwarded
        * **flags**: list of str, all the flags for this mail
        * **from**: dict, name and email of the denser
        * **to**: list of dict, list of recipients (name and email)
        * **cc**: list of dict, list of recipients in copy (name and email)
        * **reply_to**: list of dict, list of contact in reply-to header (name and email)
        * **subject**: str, subject of the mail
        * **date**: str, date of the mail
        * **return_path**: str, value of the return path
        * **has_attachment**: bool, this mail has attachment
        * **is_signed**: bool, this mail has a signature
        * **priority**: int, between 1 (highest priority) and 5 (lowest priority). 3 is normal 
        * **should_ask_receipt**: bool, this mail ask for a receipt
        * **mail_type**: list of str, say the type of mail/content (value can event or contact)

        With content, all the above plus:

        * **contents**: list of dict, each item is a content object 
        * **attachments**: list of dict, each item describe the attachment
        * **certificates**: list of dict, certificates in the mail
        * **mail_type_data**: list of dict, metadata for the mail_type (same index as mail_type)

        If you want just to list the mails while not needing the actual content,
        set `fields="contents"` and `fields_action="exclude"`.

        ---

        :param collection_param: pagination, sorting and filtering args
        :type collection_param: CollectionPaginateArgs
        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: The folder identifier
        :type folder_name: str
        :return: A tuple of (item count, API response dict, status code)
        :rtype: Tuple[int, dict, int]
        """
        logger_api.debug("Calling ApiMailFolderIdMail: Fetching mail list for account_id: %s, folder_name: %s, params: %s", account_id, folder_name, collection_param)
        interface: InterfaceApiMailMail = g.inter

        item_count, response, status_code = interface.get_mail_list(account_id, folder_name, collection_param)

        return item_count, response, status_code

@blp.route("/batch-action")
class ApiMailFolderIdAction(MethodView):
    """API to batch perform actions on all mails in a specific folder.
    """
    def post(self, batch_data: dict, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Action: Batch perform actions (tag, delete, move, spam, ham, zip, copy, forward) on selected mails in the specified folder. (NOT IMPLEMENTED)
        """
        if batch_data.get("action") == "tag":
            # Implement tagging logic here
            pass
        if batch_data.get("action") == "delete":
            pass
            # logger_api.debug("Calling ApiMailFolderIdMail: Deleting mails for account_id: %s, folder_name: %s, mail_uids: %s", account_id, folder_name, mail_data.get("mail_uids"))
            # interface: InterfaceApiMailFolder = g.inter
            # return interface.delete_mails(account_id, folder_name, mail_data["mail_uids"])
        if batch_data.get("action") == "move":
            # interface: InterfaceApiMailFolder = g.inter
            # return interface.move_mails(account_id, folder_name, move_data["mail_uids"], move_data["to_folder_name"])
            pass
        if batch_data.get("action") == "spam":
            # Implement spam logic here
            pass
        if batch_data.get("action") == "ham":
            # Implement ham logic here
            pass
        if batch_data.get("action") == "zip":
            # Implement zip logic here
            pass
        if batch_data.get("action") == "copy":
            # Implement copy logic here
            pass
        if batch_data.get("action") == "forward":
            # Implement forward logic here
            pass
        raise NotImplementedError("Batch action mails is not implemented yet.")
        # logger_api.debug("Calling ApiMailFolderIdAction.post for account_id: %s, folder_name: %s with action: %s", account_id, folder_name, batch_data.get("action"))
        # interface: InterfaceApiMailMail = g.inter
        # return interface.batch_mail_action(account_id, folder_name, batch_data)


@blp.route("/<string:mail_uid>")
class ApiMailDetail(MethodView):
    """
    API to fetch mail details.
    """

    @blp.response(200, MailDetailResponseSchema, example=MailDetailResponseSchema.example())
    def get(self, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Retrieve detailed information about a specific mail.

        :param account_id: The account identifier.
        :type account_id: str
        :param folder_name: The folder identifier.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail.
        :type mail_uid: str
        :return: Detailed mail information.
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailDetail: Fetching mail detail for account_id: %s, folder_name: %s, mail_uid: %s",
            account_id,
            folder_name,
            mail_uid,
        )
        interface: InterfaceApiMailMail = g.inter
        return interface.get_mail_detail(account_id, folder_name, mail_uid)

    @blp.response(204, MailDeleteResponseSchema, example=MailDeleteResponseSchema.example())
    def delete(self, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Delete a specific mail (mark as deleted)

        Resource, delete (mark as deleted) a specific mail

        :param account_id: The account identifier.
        :type account_id: str
        :param folder_name: The folder identifier.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail.
        :type mail_uid: str
        :return: A response indicating the result of the deletion.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailDetail.delete for account_id: %s, folder_name: %s, mail_uid: %s", account_id, folder_name, mail_uid)
        interface: InterfaceApiMailMail = g.inter
        return interface.delete_mail(account_id, folder_name, mail_uid)



@blp.route("/<string:mail_uid>/action")
class ApiMailDetailAction(MethodView):
    """API to manage actions on a specific mail.
    """
    @blp.arguments(MailActionSchema, example=MailActionSchema.example(), error_status_code=400)
    @blp.response(200)
    def post(self, data: dict, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Perform an action (tag, untag, move, spam, ham, copy) on a specific mail in the specified folder.

        :param data: The action data containing 'action' and optional 'data' field
        :type data: dict
        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: The folder identifier
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: A response indicating the result of the action
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailDetailAction.post for account_id: %s, folder_name: %s, mail_uid: %s with action: %s",
            account_id,
            folder_name,
            mail_uid,
            data["action"]
        )
        interface: InterfaceApiMailMail = g.inter

        return interface.mail_action(account_id, folder_name, mail_uid, data)



@blp.route("/<string:mail_uid>/download")
class ApiMailDetailDownload(MethodView):
    """API to download a specific mail as .eml or .zip.
    """
    @blp.arguments(MailDownloadSchema, example=MailDownloadSchema.example(), error_status_code=400)
    def post(self, data: dict, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Download a specific mail in the specified folder as .eml or .zip.

        :param data: The download data containing 'format' field ('eml' or 'zip')
        :type data: dict
        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: The folder identifier
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: The mail file as an attachment
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailDetailDownload.post for account_id: %s, folder_name: %s, mail_uid: %s with format: %s",
            account_id,
            folder_name,
            mail_uid,
            data["format"]
        )
        interface: InterfaceApiMailMail = g.inter

        result = interface.download_mail(account_id, folder_name, mail_uid, data["format"])

        if isinstance(result, tuple):
            return result

        if data["format"] == "zip":
            filename = f"mail_{mail_uid}.zip"
            mimetype = "application/zip"
        else:
            filename = f"mail_{mail_uid}.eml"
            mimetype = "message/rfc822"

        return send_file(
            result,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )


@blp.route("/<string:mail_uid>/edit")
class ApiMailDetailEdit(MethodView):
    """API to open a mail for editing by creating a new tmp_draft entry."""

    @blp.response(200, MailEditResponseSchema, example=MailEditResponseSchema.example())
    def get(self, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Open an existing mail for editing.

        Fetches the mail identified by *mail_uid* from *folder_name*, copies it into
        the Drafts folder as a new IMAP draft, and registers it in the tmp_draft table.
        Returns the full mail content together with the newly created tmp_draft ``key``
        that must be supplied to subsequent draft endpoints (save, upload attachment, send…).

        :param account_id: The account identifier.
        :type account_id: str
        :param folder_name: The folder containing the source mail.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail to edit.
        :type mail_uid: str
        :return: Parsed mail data with an additional ``key`` field.
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailDetailEdit.get for account_id: %s, folder_name: %s, mail_uid: %s",
            account_id,
            folder_name,
            mail_uid,
        )
        interface: InterfaceApiMailMail = g.inter
        return interface.open_mail_for_edit(account_id, folder_name, mail_uid)


@blp.route("/<string:mail_uid>/reply")
class ApiMailDetailReply(MethodView):
    """API to prepare a reply to a specific mail."""

    @blp.response(200, MailReplyResponseSchema, example=MailReplyResponseSchema.example())
    def get(self, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Prepare a reply draft for a specific mail.

        Fetches the original mail, extracts its RFC 5322 ``Message-ID`` and
        ``References`` headers, creates a new empty draft in the Drafts folder,
        then registers a new ``tmp_draft`` row whose ``headers`` column contains
        the pre-filled ``In-Reply-To`` and ``References`` values ready to be
        injected when the reply is eventually sent.

        Returns the ``key`` (tmp_draft key) and all the necessary information to pre-fill the reply form

        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: The folder containing the source mail.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail to reply to.
        :type mail_uid: str
        :return: Dict with ``key``
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailDetailReply.get for account_id: %s, folder_name: %s, mail_uid: %s",
            account_id,
            folder_name,
            mail_uid,
        )
        interface: InterfaceApiMailMail = g.inter
        return interface.reply_mail(account_id, folder_name, mail_uid)


@blp.route("/<string:mail_uid>/raw")
class ApiMailDetailRaw(MethodView):
    """API to fetch the raw content of a specific mail. 
    """
    @blp.response(200, MailRawResponseSchema, example=MailRawResponseSchema.example())
    def get(self, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Retrieve the raw content of a specific mail in the specified folder.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: A tuple of (API response dict, status code)
        :rtype: Tuple[Dict[str, Any], int]
        """
        logger_api.debug("Calling ApiMailDetailRaw.get for account_id: %s, folder_name: %s, mail_uid: %s", account_id, folder_name, mail_uid)
        interface: InterfaceApiMailMail = g.inter
        return interface.get_mail_raw(account_id, folder_name, mail_uid)


@blp.route("/<string:mail_uid>/attachments/<path:filename>")
class ApiMailDetailAttachmentDownload(MethodView):
    """API to download a specific attachment from a mail."""

    def get(self, account_id: str, folder_name: str, mail_uid: str, filename: str) -> ResponseReturnValue:
        """Download a specific attachment from a mail.

        :param account_id: The account identifier.
        :type account_id: str
        :param folder_name: The folder containing the mail.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail.
        :type mail_uid: str
        :param filename: The filename of the attachment to download.
        :type filename: str
        :return: The attachment file as a download response, or an error response.
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailDetailAttachmentDownload.get for account_id: %s, folder_name: %s, mail_uid: %s, filename: %s",
            account_id,
            folder_name,
            mail_uid,
            filename,
        )
        interface: InterfaceApiMailMail = g.inter
        result = interface.download_attachment(account_id, folder_name, mail_uid, filename)

        if isinstance(result, tuple) and not isinstance(result[0], bytes):
            return result

        attachment_bytes, content_type = result
        return send_file(
            BytesIO(attachment_bytes),
            mimetype=content_type,
            as_attachment=True,
            download_name=filename,
        )
