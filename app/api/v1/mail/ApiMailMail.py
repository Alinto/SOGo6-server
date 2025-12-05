from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailMail import InterfaceApiMailMail
from app.utils.logger.logger import logger_api
from .schemas.mail import MailDetailResponseSchema

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailDetail", __name__, url_prefix="/mailboxes/<int:account_id>/folders/<folder_name>/mails")


@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.

    Provide user_conf as either a single dict or a list of dicts (accounts).
    Example below provides two accounts (primary index 0, secondary index 1).
    """
    logger_api.debug("Calling before_request for ApiMailDetail")
    process: ProcessSetting = g.process

    user_conf_test = [
        {
            "username": "tkeriven@snapshot.alinto.org",
            "password": "Banane2!",
            "type": "imap",
            "server": "192.168.69.31",
            "port": 10143
        },
        {
            "username": "tkeriven3@snapshot.alinto.org",
            "password": "Banane01!",
            "type": "imap",
            "server": "192.168.69.31",
            "port": 10143
        }
    ]

    interface_api = InterfaceApiMailMail(
        process_setting=process,
        user_conf=user_conf_test,
    )
    g.inter = interface_api


@blp.route("")
class ApiMailFolderIdMail(MethodView):
    """
    API to list mails in a specific mail folder
    """

    @blp.paginate(page=1, page_size=20, max_page_size=100)
    @blp.response(200)
    def get(self, pagination_parameters: 'FakePaginationParameters', account_id: int, folder_name: str) -> ResponseReturnValue:
        """Fetch the list of mails in a specific folder.

        Get the list of mails in a specific folder

        :param pagination_parameters: Flask-Smorest pagination parameters
        :type pagination_parameters: FakePaginationParameters
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A list of mails in the specified folder with pagination info
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailFolderIdMail: Fetching mail list for account_id: %s, folder_name: %s, first: %s, last: %s",
            account_id, folder_name, pagination_parameters.first_item, pagination_parameters.last_item
        )
        interface: InterfaceApiMailMail = g.inter
        first = pagination_parameters.first_item
        last = pagination_parameters.last_item
        pagination_parameters.item_count, ret, status = interface.get_mail_list(account_id, folder_name, first, last)
        return ret, status


@blp.route("/batch-action")
class ApiMailFolderIdAction(MethodView):
    """API to batch perform actions on all mails in a specific folder.
    """
    def post(self, batch_data: dict, account_id: int, folder_name: str) -> ResponseReturnValue:
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
        logger_api.debug("Calling ApiMailFolderIdAction.post for account_id: %s, folder_name: %s with action: %s", account_id, folder_name, batch_data.get("action"))
        interface: InterfaceApiMailMail = g.inter
        return interface.batch_mail_action(account_id, folder_name, batch_data)


@blp.route("/<int:mail_uid>")
class ApiMailDetail(MethodView):
    """
    API to fetch mail details.
    """

    @blp.response(200, MailDetailResponseSchema)
    def get(self, account_id: int, folder_name: str, mail_uid: int) -> ResponseReturnValue:
        """Retrieve detailed information about a specific mail.

        Resource, get detailed information about a specific mail

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_name: The folder identifier.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail.
        :type mail_uid: int
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

    def delete(self, account_id: int, folder_name: str, mail_uid: int) -> ResponseReturnValue:
        """Delete a specific mail (mark as deleted). (NOT IMPLEMENTED)

        Resource, delete (mark as deleted) a specific mail

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_name: The folder identifier.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail.
        :type mail_uid: int
        :return: A response indicating the result of the deletion.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailDetail.delete for account_id: %s, folder_name: %s, mail_uid: %s", account_id, folder_name, mail_uid)
        interface: InterfaceApiMailMail = g.inter
        return interface.delete_mail(account_id, folder_name, mail_uid)



@blp.route("/<int:mail_uid>/action")
class ApiMailDetailAction(MethodView):
    """API to manage actions on a specific mail.
    """
    def post(self, data: dict, account_id: int, folder_name: str, mail_uid: int) -> ResponseReturnValue:
        """Action: Perform an action (tag, move, spam, ham, download, zip, copy) on a specific mail in the specified folder. (NOT IMPLEMENTED)
        """
        if data.get("action") == "tag":
            # Implement tagging logic here
            pass
        if data.get("action") == "move":
            # Implement move logic here
            pass
        if data.get("action") == "spam":
            # Implement spam logic here
            pass
        if data.get("action") == "ham":
            # Implement ham logic here
            pass
        if data.get("action") == "download":
            # Implement download logic here
            pass
        if data.get("action") == "zip":
            # Implement zip logic here
            pass
        if data.get("action") == "copy":
            # Implement copy logic here
            pass
        raise NotImplementedError("Mail actions are not implemented yet.")
        # logger_api.debug("Calling ApiMailDetailAction.post for account_id: %s, folder_name: %s, mail_uid: %s with action: %s", account_id, folder_name, mail_uid, data.get("action"))
        # interface: InterfaceApiMailMail = g.inter
        # return interface.mail_action(account_id, folder_name, mail_uid, data)


@blp.route("/<int:mail_uid>/reply")
class ApiMailDetailReply(MethodView):
    """API to manage replies to a specific mail.
    """
    def post(self, account_id: int, folder_name: str, mail_uid: int) -> ResponseReturnValue:
        """Action: Reply to a specific mail in the specified folder. (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailDetailReply.post for account_id: %s, folder_name: %s, mail_uid: %s", account_id, folder_name, mail_uid)
        interface: InterfaceApiMailMail = g.inter
        return interface.reply_mail(account_id, folder_name, mail_uid)

@blp.route("/<int:mail_uid>/forward")
class ApiMailDetailForward(MethodView):
    """API to manage forwards of a specific mail.
    """
    def post(self, account_id: int, folder_name: str, mail_uid: int) -> ResponseReturnValue:
        """Action: Forward a specific mail in the specified folder. (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailDetailForward.post for account_id: %s, folder_name: %s, mail_uid: %s", account_id, folder_name, mail_uid)
        interface: InterfaceApiMailMail = g.inter
        return interface.forward_mail(account_id, folder_name, mail_uid)

@blp.route("/<int:mail_uid>/raw")
class ApiMailDetailRaw(MethodView):
    """API to fetch the raw content of a specific mail. 
    """
    def get(self, account_id: int, folder_name: str, mail_uid: int) -> ResponseReturnValue:
        """Retrieve the raw content of a specific mail in the specified folder.
        """
        logger_api.debug("Calling ApiMailDetailRaw.get for account_id: %s, folder_name: %s, mail_uid: %s", account_id, folder_name, mail_uid)
        interface: InterfaceApiMailMail = g.inter
        return interface.get_mail_raw(account_id, folder_name, mail_uid)
