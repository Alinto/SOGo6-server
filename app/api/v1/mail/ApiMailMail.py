from __future__ import annotations
from typing import TYPE_CHECKING

from io import BytesIO

from flask import g, send_file
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailMail import InterfaceApiMailMail
from app.utils.logger.logger import logger_api
from app.utils.api.paginate_sort_filter import custom_paginate, CustomPaginateResponse
from .schemas.mail import (
    MailDetailResponseSchema,
    MailListResponseSchema,
    MailDeleteResponseSchema,
    MailRawResponseSchema,
    MailActionSchema,
)

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User

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
    @custom_paginate(blp)
    def get(self, first: int, last: int, fields_args: dict, sort_args: dict, account_id: str, folder_name: str) -> CustomPaginateResponse:
        """Fetch the list of mails in a specific folder.

        :param first: The index of the first mail to retrieve (for pagination)
        :type first: int
        :param last: The index of the last mail to retrieve (for pagination)
        :type last: int
        :param fields_args: The fields to include in the response (for field filtering)
        :type fields_args: dict
        :param sort_args: The sorting parameters (for sorting)
        :type sort_args: dict
        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: The folder identifier
        :type folder_name: str
        :return: A tuple of (item count, API response dict, status code)
        :rtype: Tuple[int, dict, int]
        """
        logger_api.debug(
            "Calling ApiMailFolderIdMail: Fetching mail list for account_id: %s, folder_name: %s, first: %s, last: %s, sort_by: %s, sort_order: %s, fields: %s",
            account_id, folder_name,
            first, last,
            sort_args.get("sort_by"), sort_args.get("sort_order"),
            fields_args.get("include_fields"),
        )
        interface: InterfaceApiMailMail = g.inter

        item_count, response, status_code = (
            interface.get_mail_list(account_id, folder_name, first, last)
        )

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
        :type account_id: int
        :param folder_name: The folder identifier
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
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

        ret, http_code = interface.mail_action(account_id, folder_name, mail_uid, data)
        if data["action"] in ("download", "zip"):
            if data["action"] == "download":
                filename = f"mail_{mail_uid}.eml"
            else:
                filename = f"mail_{mail_uid}.zip"
            #TODO separate download/zip 
            return send_file(
                ret,  # type: ignore[arg-type]
                mimetype="message/rfc822",
                as_attachment=True,
                download_name = filename
            )

        return ret, http_code



@blp.route("/<string:mail_uid>/reply")
class ApiMailDetailReply(MethodView):
    """API to manage replies to a specific mail.
    """
    def post(self, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Action: Reply to a specific mail in the specified folder. (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailDetailReply.post for account_id: %s, folder_name: %s, mail_uid: %s", account_id, folder_name, mail_uid)
        interface: InterfaceApiMailMail = g.inter
        return interface.reply_mail(account_id, folder_name, mail_uid)

@blp.route("/<string:mail_uid>/forward")
class ApiMailDetailForward(MethodView):
    """API to manage forwards of a specific mail.
    """
    def post(self, account_id: str, folder_name: str, mail_uid: str) -> ResponseReturnValue:
        """Action: Forward a specific mail in the specified folder. (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailDetailForward.post for account_id: %s, folder_name: %s, mail_uid: %s", account_id, folder_name, mail_uid)
        interface: InterfaceApiMailMail = g.inter
        return interface.forward_mail(account_id, folder_name, mail_uid)

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
