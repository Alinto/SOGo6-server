from __future__ import annotations
from typing import TYPE_CHECKING

from flask import request, g, jsonify, make_response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint
from marshmallow import Schema

from app.interface.mail.InterfaceApiMailFolder import InterfaceApiMailFolder
from app.utils.logger.logger import logger_api
from app.utils.exceptions import RequestException
from app.utils.api.ApiResponse import ApiBaseResponse
from .schemas.mailDelete import MailDeleteSchema, MailFolderQueryArgsSchema
from .schemas.mailMove import MailMoveSchema
from .schemas.mailList import MailMessageListResponseSchema, MailListQuerySchema

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailFolder", __name__, url_prefix="/mail")

class EmptySchema(Schema):
    """Empty schema for requests without body"""


@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.

    Provide user_conf as either a single dict or a list of dicts (accounts).
    Here we provide a list: index 0 = primary, index 1 = secondary.
    """
    logger_api.debug("Calling before_request for ApiMailFolder")
    process: ProcessSetting = g.process

    user_conf_test = [
        {
            "username": "tkeriven@snapshot.alinto.org",
            "password": "Banane2!",
            "type": "imap",
            "server": "192.168.69.31",
            "port": 10143,
            #"auth_mech": "plain" #TODO: revoir ça
        },
        {
            "username": "tkeriven3@snapshot.alinto.org",
            "password": "Banane01!",
            "type": "imap",
            "server": "192.168.69.31",
            "port": 10143
        }
    ]

    interface_api = InterfaceApiMailFolder(
        process_setting=process,
        user_conf=user_conf_test,
    )
    g.inter = interface_api

@blp.route("/<int:account_id>/folder/<folder_name>")
class ApiMailFolderId(MethodView):
    """
    API to manage a specific mail folder.
    """

    @blp.arguments(EmptySchema, location="json", required=False)    # TODO: pour le moment seule solution trouvé pour accepter un DELETE sans body
    @blp.response(204)
    def delete(self, _json: dict, account_id: int, folder_name: str) -> ResponseReturnValue:
        """Delete a specific mail folder.

        :param _json: Empty JSON data (ignored)
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder to delete
        :type folder_name: str
        :return: A response indicating the result of the deletion
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderId: Deleting folder for account_id: %s, folder_name: %s", account_id, folder_name)
        interface: InterfaceApiMailFolder = g.inter
        return interface.delete_folder(account_id, folder_name)


@blp.route("/<int:account_id>/folder/<folder_name>/mail")
class ApiMailFolderIdMail(MethodView):
    """
    API to list mails in a specific mail folder
    """

    @blp.arguments(MailListQuerySchema, location="query", as_kwargs=True)
    @blp.response(200, MailMessageListResponseSchema)
    def get(self, account_id: int, folder_name: str, page: int = 1, per_page: int = 20) -> ResponseReturnValue:
        """Fetch the list of mails in a specific folder.

        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param page: Page number for pagination
        :type page: int
        :param per_page: Number of mails per page
        :type per_page: int
        :return: A list of mails in the specified folder with pagination info
        :rtype: ResponseReturnValue
        """
        logger_api.debug(
            "Calling ApiMailFolderIdMail: Fetching mail list for account_id: %s, folder_name: %s, page: %s, per_page: %s",
            account_id, folder_name, page, per_page
        )

        interface: InterfaceApiMailFolder = g.inter
        try:
            result = interface.get_mail_list(account_id, folder_name, page=page, per_page=per_page)

            # Create the response object
            response = make_response(jsonify(result))

            # Add the total count in header
            total_count = result.get("total", 0)
            response.headers["X-Total-Count"] = str(total_count)
            response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

            return response

        except RequestException as e:
            logger_api.error("RequestException in get_mail_list: %s", e)
            return jsonify({"status": False, "data": [], "errors": str(e)}), 400

@blp.route("/<int:account_id>/folder/<folder_name>/mail/delete")
class ApiMailFolderIdMailDelete(MethodView):
    """
    API to delete mails (mark as deleted) in a specific mail folder.
    """
    @blp.arguments(MailDeleteSchema)
    @blp.response(200, ApiBaseResponse)
    def post(self, mail_data: dict, account_id: int, folder_name: str) -> ResponseReturnValue:
        """Delete mails in a specific folder.

        :param mail_data: The data containing mail IDs to delete
        :type mail_data: dict
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A response indicating the result of the deletion
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderIdMail: Deleting mails for account_id: %s, folder_name: %s, mail_uids: %s", account_id, folder_name, mail_data.get("mail_uids"))
        interface: InterfaceApiMailFolder = g.inter
        return interface.delete_mails(account_id, folder_name, mail_data["mail_uids"])



@blp.route("/<int:account_id>/folder/<folder_name>/mail/all")
class ApiMailFolderIdMailAll(MethodView):
    """API to delete all mails in a specific folder."""

    @blp.arguments(MailFolderQueryArgsSchema, location="query", required=False)
    @blp.arguments(EmptySchema, location="json", required=False)
    @blp.response(204, ApiBaseResponse)
    def delete(
        self,
        query_args: dict,
        _json: dict,
        account_id: int,
        folder_name: str
    ) -> ResponseReturnValue:
        """Delete all mails in a specific folder.
        
        :param query_args: Query arguments containing optional before_date
        :type query_args: dict
        :param _json: Empty JSON data (ignored)
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A response indicating the result of the delete operation
        :rtype: ResponseReturnValue
        """
        before_date = query_args.get("before_date")
        logger_api.debug(
            "Deleting all mails before %s for account_id=%s folder_name=%s",
            before_date, account_id, folder_name
        )

        interface: InterfaceApiMailFolder = g.inter
        try:
            result = interface.delete_all_mail_in_folder(account_id, folder_name, before_date)
            if result.get("status"):
                return ("", 204)
            return jsonify({"status": False, "data": {}, "errors": result.get("errors")}), 400
        except RequestException as e:
            logger_api.error("RequestException: %s", e)
            return jsonify({"status": False, "data": {}, "errors": str(e)}), 400


@blp.route("/<int:account_id>/folder/<folder_name>/mail/move")
class ApiMailBulkMove(MethodView):
    """API to move mails from one folder to another.
    """
    @blp.arguments(MailMoveSchema)
    @blp.response(200, ApiBaseResponse)
    def post(self, move_data: dict, account_id: int, folder_name: str) -> ResponseReturnValue:
        """Move mails from one folder to another.

        :param move_data: The data containing mail IDs and the target folder ID
        :type move_data: dict
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the source folder
        :type folder_name: str
        :return: A response indicating the result of the move operation
        :rtype: ResponseReturnValue
        """
        interface: InterfaceApiMailFolder = g.inter
        try:
            return interface.move_mails(account_id, folder_name, move_data["mail_uids"], move_data["to_folder_name"])
        except RequestException as e:
            logger_api.error("RequestException in move_mails: %s", e)
            return jsonify({"status": False, "data": {}, "errors": str(e)}), 400



@blp.route("/<int:account_id>/folder/<folder_name>/expunge")
class ApiMailFolderIdExpunge(MethodView):
    """API to expunge all mails in a specific folder.
    """
    @blp.arguments(EmptySchema, location="json", required=False)    # TODO: pour le moment seule solution trouvé pour accepter un DELETE sans body
    @blp.response(204, ApiBaseResponse)
    def delete(self, _json: dict, account_id: int, folder_name: str) -> ResponseReturnValue:
        """Expunge all mails in the specified folder.

        :param _json: Parsed body (EmptySchema) — unused but consumed by blp.arguments.
        :param account_id: The ID of the account
        :type account_id: int
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A response indicating the result of the expunge operation
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderIdExpunge: Expunging folder for account_id: %s, folder_name: %s", account_id, folder_name)
        interface: InterfaceApiMailFolder = g.inter
        try:
            result = interface.expunge_folder(account_id, folder_name)
            if result.get("status"):
                return ("", 204)
            return jsonify({"status": False, "data": {}, "errors": result.get("errors")}), 400
        except RequestException as e:
            logger_api.error("RequestException in expunge_folder: %s", e)
            return jsonify({"status": False, "data": {}, "errors": str(e)}), 400
