from __future__ import annotations
from typing import TYPE_CHECKING

from flask import request, g, jsonify
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailFolder import InterfaceApiMailFolder
from app.utils.logger.logger import logger_api
from .schemas.mailDelete import MailDeleteSchema
from .schemas.mailMove import MailMoveSchema
from .schemas.mailList import MailMessageListResponseSchema
#from .schemas.folderCreate import FolderCreateSchema


if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailFolder", __name__, url_prefix="/account")

@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.
    """
    logger_api.debug("Calling before_request for ApiMailFolder")
    process: ProcessSetting = g.process
    interface_api = InterfaceApiMailFolder()
    g.inter = interface_api

@blp.route("/<int:account_id>/folder/<folder_id>")
class ApiMailFolderId(MethodView):
    """
    API to manage a specific mail folder.
    """

    @blp.response(204)
    def delete(self, account_id: int, folder_id: str) -> ResponseReturnValue:
        """
        Delete a specific mail folder for a given account.

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :return: Empty response with 204 status code.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderId: Deleting folder for account_id: %s, folder_id: %s", account_id, folder_id)
        interface: InterfaceApiMailFolder = g.inter
        return interface.delete_folder(account_id, folder_id)


@blp.route("/<int:account_id>/folder/<folder_id>/mail")
class ApiMailFolderIdMail(MethodView):
    """
    API to list mails and to delete mails (mark as deleted) in a specific mail folder
    """

    @blp.response(200, MailMessageListResponseSchema)
    def get(self, account_id: int, folder_id: str) -> ResponseReturnValue:
        """
        Retrieve the list of mails in a given folder.

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :return: List of mails with parsed headers and attachment info.
        :rtype: ResponseReturnValue
        :raises RequestException: If the folder cannot be found or mails cannot be retrieved.
        Query params:
            page: int (default: 1)
            per_page: int (default: 20)
        """
        logger_api.debug("Calling ApiMailFolderIdMail: Fetching mail list for account_id: %s, folder_id: %s", account_id, folder_id)
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        interface: InterfaceApiMailFolder = g.inter
        return interface.get_mail_list(account_id, folder_id, page=page, per_page=per_page)

    @blp.arguments(MailDeleteSchema)
    @blp.response(200)
    def delete(self, mail_data: dict, account_id: int, folder_id: str) -> ResponseReturnValue:
        """
        Delete multiple mails from a folder.

        :param mail_data: The mail data containing the list of mail IDs to delete.
        :type mail_data: dict
        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :return: JSON with lists of deleted and failed mail IDs.
        :rtype: ResponseReturnValue
        :raises RequestException: If the folder cannot be found or mails cannot be deleted.

        Request body: { "mail_ids": [1, 2, 3] }
        """
        logger_api.debug("Calling ApiMailFolderIdMail: Deleting mails for account_id: %s, folder_id: %s, mail_ids: %s", account_id, folder_id, mail_data.get("mail_ids"))
        interface = g.inter  # type: InterfaceApiMailFolder
        result = interface.delete_mails(account_id, folder_id, mail_data["mail_ids"])
        if not result.get("success"):
            return jsonify({"error": result.get("error", "Failed to delete mails")}), 400
        return jsonify({
            "deleted": result.get("deleted_ids", []),
            "failed": result.get("failed_ids", []),
        })


@blp.route("/<int:account_id>/folder/<folder_id>/mail/all")
class ApiMailFolderIdMailAll(MethodView):
    """
    API to list mails and to delete mails (mark as deleted) in a specific mail folder
    """
    def delete(self, account_id: int, folder_id: str) -> ResponseReturnValue:
        """
        Mark as deleted all mails in folder before a given date.

        Query param:
            before: date string (YYYY-MM-DD)

        Returns:
            JSON with success or error.
        """
        before_date = request.args.get("before")
        logger_api.debug("Calling ApiMailFolderIdMailAll: Deleting all mails before %s, for account_id: %s, folder_id: %s", before_date, account_id, folder_id)
        interface: InterfaceApiMailFolder = g.inter
        return interface.delete_all_mail_in_folder(account_id, folder_id, before_date)



@blp.route("/<int:account_id>/folder/<folder_id>/mail/move")
class ApiMailBulkMove(MethodView):
    """
    API to move multiple mails to another folder.
    """

    @blp.arguments(MailMoveSchema)
    @blp.response(200)
    def post(self, move_data: dict, account_id: int, folder_id: str) -> ResponseReturnValue:
        """
        Move multiple mails from a folder to another folder.

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The source folder identifier.
        :type folder_id: str
        :param move_data: The mail move data containing the list of mail IDs and target folder ID.
        :type move_data: dict
        :return: JSON with lists of moved and failed mail IDs.
        :rtype: ResponseReturnValue
        :raises RequestException: If the folder cannot be found or mails cannot be moved.

        Request body: { "mail_ids": [1,2,3], "to_folder_id": "TargetFolder" }
        """
        interface = g.inter  # type: InterfaceApiMailFolder
        return interface.move_mails(account_id, folder_id, move_data["mail_ids"], move_data["to_folder_id"])


@blp.route("/<int:account_id>/folder/<folder_id>/expunge")
class ApiMailFolderIdExpunge(MethodView):
    """
    API endpoint to expunge mails marked as deleted from a folder.
    """

    @blp.response(204)
    def delete(self, account_id: int, folder_id: str) -> ResponseReturnValue:
        """
        Expunge mails marked as deleted from the specified folder.

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder name.
        :type folder_id: str
        :return: Success or error message.
        """
        logger_api.debug("Calling ApiMailFolderIdExpunge: Expunging folder for account_id: %s, folder_id: %s", account_id, folder_id)
        interface: InterfaceApiMailFolder = g.inter
        return interface.expunge_folder(account_id, folder_id)


#@blp.route("/<int:account_id>/folder/<folder_id>/subfolder")
#class ApiMailSubfolderCreate(MethodView):
#    """
#    API endpoint to create a new subfolder in a given folder.
#    """
#
#    @blp.arguments(FolderCreateSchema)
#    def post(self, folder_data: dict, account_id: int, folder_id: str) -> ResponseReturnValue:
#        """
#        Create a new subfolder in the specified folder.
#
#        Request body: { "name": "NewSubFolder" }
#        """
#        interface: InterfaceApiMailFolder = g.inter
#        return interface.create_subfolder(account_id, folder_id, folder_data["name"])



#     @blp.arguments(MailDetailSchema)    #renvoie un 422 UNPROCESSABLE ENTITY au lieu d'un 400 BAD REQUEST???
#     @blp.response(201, MailDetailSchema())
#     def post(self, mail_data: dict, account_id: int, folder_id: str) -> ResponseReturnValue:
#         """
#         Add a new mail to the specified folder.

#         The incoming JSON is validated against MailDetailSchema. If the folder does not
#         exist, a 404 error is returned. The mail is not actually stored (database not ready).

#         :param mail_data: The mail data to be added, validated by MailDetailSchema.
#         :type mail_data: dict
#         :param account_id: The account identifier.
#         :type account_id: int
#         :param folder_id: The id of the folder to add the mail to.
#         :type folder_id: str
#         :return: The added mail data.
#         :rtype: ResponseReturnValue
#         :raises RequestException: If the folder cannot be found.
#         """
#         interface: InterfaceApiMailFolder = g.inter
#         try:
#             return interface.add_mail_in_folder(account_id, folder_id, mail_data)
#         except RequestException as e:
#             abort(404, message=str(e))
#             return {}
