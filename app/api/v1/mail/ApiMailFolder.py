from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint
from marshmallow import Schema

from app.interface.mail.InterfaceApiMailFolder import InterfaceApiMailFolder
from app.utils.logger.logger import logger_api
from .schemas.folder import (
    FolderCreateSchema,
    FolderUpdateSchema,
    FolderPurgeSchema,
    FolderShareSchema,
    FolderListResponseSchema,
    FolderCreateResponseSchema,
    FolderDetailsResponseSchema,
    FolderUpdateResponseSchema,
    FolderExpungeSchema,
    FolderExpungeResponseSchema,
    FolderPurgeResponseSchema,
    FolderShareResponseSchema,
)

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User

blp = Blueprint("Mail Folder", __name__, url_prefix="/mailboxes/<string:account_id>/folders")

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
    process: ProcessSetting = g.process_settings
    user_domain_settings: dict = g.user_domain_settings
    user: User = g.user

    interface_api = InterfaceApiMailFolder(
        process_setting=process,
        user_domain_settings=user_domain_settings,
        user=user
    )
    g.inter = interface_api


@blp.route("")
class ApiMailAccount(MethodView):
    """
    Ressource: API to manage mail folders for a given account.
    """

    @blp.response(200, FolderListResponseSchema, example=FolderListResponseSchema.example())
    def get(self, account_id: str) -> ResponseReturnValue:
        """
        Get the list of mail folders for a given account

        :param account_id: The account identifier (0 = primary, 1 = secondary).
        :type account_id: str
        :return: ApiBaseResponse with folder list
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailAccount: Fetching folder list for account_id: %s", account_id)
        interface: InterfaceApiMailFolder = g.inter
        return interface.get_folder_list(account_id)


    @blp.arguments(FolderCreateSchema, example=FolderCreateSchema.example())
    @blp.response(201, FolderCreateResponseSchema, example=FolderCreateResponseSchema.example())
    def post(self, folder_data: dict, account_id: str) -> ResponseReturnValue:
        """
        Create a new mail folder for a given account

        :param folder_data: The folder data containing the name.
        :type folder_data: dict
        :param account_id: The account identifier (0 = primary, 1 = secondary).
        :type account_id: str
        :return: ApiBaseResponse with created folder info
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailAccount: Creating folder for account_id: %s with data: %s", account_id, folder_data)
        interface: InterfaceApiMailFolder = g.inter
        return interface.create_folder(account_id, folder_name=folder_data["name"], parent_path=folder_data["parent"])


@blp.route("/<path:folder_name>")
class ApiMailFolderId(MethodView):
    """
    API to manage a specific mail folder.
    """

    @blp.response(204)
    def delete(self, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Delete a specific mail folder.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder to delete
        :type folder_name: str
        :return: A response indicating the result of the deletion
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderId: Deleting folder for account_id: %s, folder_name: %s", account_id, folder_name)
        interface: InterfaceApiMailFolder = g.inter
        return interface.delete_folder(account_id, folder_name)

    @blp.arguments(FolderUpdateSchema, example=FolderUpdateSchema.example())
    @blp.response(200, FolderUpdateResponseSchema, example=FolderUpdateResponseSchema.example())
    def patch(self, folder_data: dict, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Update name, type (junk, template...) and subscription status of a specific mail folder.
        Notimplemented to rework how to set a type, rename, susbribed...

        :param folder_data: The folder update data (name, subscribed, type).
        :type folder_data: dict
        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: The current name of the folder
        :type folder_name: str
        :return: ApiBaseResponse with updated folder info
        :rtype: ResponseReturnValue
        """
        raise NotImplementedError()
        logger_api.debug("Calling ApiMailFolderId.patch for account_id: %s, folder_name: %s with data: %s", account_id, folder_name, folder_data)
        interface: InterfaceApiMailFolder = g.inter
        return interface.update_folder(account_id, folder_name, folder_data)

    @blp.response(200, FolderDetailsResponseSchema, example=FolderDetailsResponseSchema.example())
    def get(self, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Retrieve details of a specific mail folder.
        """
        logger_api.debug("Calling ApiMailFolderId.get for account_id: %s, folder_name: %s", account_id, folder_name)
        interface: InterfaceApiMailFolder = g.inter
        return interface.get_one_folder(account_id, folder_name)



@blp.route("/<path:folder_name>/expunge")
class ApiMailFolderIdExpunge(MethodView):
    """API to expunge all mails in a specific folder.
    """
    @blp.arguments(FolderExpungeSchema, example=FolderExpungeSchema.example())
    @blp.response(200, FolderExpungeResponseSchema, example=FolderExpungeResponseSchema.example())
    def post(self, expunge_data:dict, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Action: Expunge (compact) all mails in the specified folder.

        Action: permanently remove deleted mails from the mailbox.
        Returns the number of mails that were permanently deleted.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: ApiBaseResponse with mail_deleted count
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderIdExpunge: Expunging folder for account_id: %s, folder_name: %s", account_id, folder_name)
        interface: InterfaceApiMailFolder = g.inter
        return interface.expunge_folder(account_id, folder_name, expunge_data)


@blp.route("/<path:folder_name>/purge")
class ApiMailFolderIdPurge(MethodView):
    """API to purge all mails in a specific folder older than a given date.
    """
    @blp.arguments(FolderPurgeSchema, example=FolderPurgeSchema.example())
    @blp.response(200, FolderPurgeResponseSchema, example=FolderPurgeResponseSchema.example())
    def post(self, purge_data: dict, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Action: Purge all mails in the specified folder.
        
        Mark mails as deleted (optionally before a specific date).
        If permanently_delete is True, also expunge the folder to permanently remove deleted mails.
        
        :param purge_data: The purge configuration (do_subfolders, permanently_delete, date)
        :type purge_data: dict
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A response indicating the result of the purge operation
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderIdPurge.post for account_id: %s, folder_name: %s with data: %s",
                        account_id, folder_name, purge_data)
        interface: InterfaceApiMailFolder = g.inter
        return interface.purge_folder_mails(account_id, folder_name, purge_data)


@blp.route("/<path:folder_name>/export")
class ApiMailFolderIdExport(MethodView):
    """API to export all mails in a specific folder. 
    """
    def post(self, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Action: Export all mails in the specified folder. (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailFolderIdExport.post for account_id: %s, folder_name: %s", account_id, folder_name)
        interface: InterfaceApiMailFolder = g.inter
        return interface.export_folder_mails(account_id, folder_name)



@blp.route("/<path:folder_name>/share")
class ApiMailFolderIdShare(MethodView):
    """API to share a specific mail folder.
    """
    @blp.response(200, FolderShareResponseSchema, example=FolderShareResponseSchema.example())
    def get(self, account_id: str, folder_name: str) -> ResponseReturnValue:    #TODO: pagination?
        """Get share information for the specified folder.
        
        Returns the list of users who have access to this folder and their permissions.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: ApiBaseResponse with share information
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderIdShare.get for account_id: %s, folder_name: %s", account_id, folder_name)
        interface: InterfaceApiMailFolder = g.inter
        return interface.get_folder_share(account_id, folder_name)

    @blp.arguments(FolderShareSchema(many=True), example=FolderShareSchema.example(), error_status_code=400) #type: ignore [arg-type]
    @blp.response(200, FolderShareResponseSchema, example=FolderShareResponseSchema.example())
    def post(self, share_data: list, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Action: Share the specified folder with another user.
        
        Sets ACL permissions on the folder for the specified users.
        The request body should be a list of user objects with their rights.
        
        :param share_data: List of users with their rights configuration
        :type share_data: list
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: ApiBaseResponse with share result
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderIdShare.post for account_id: %s, folder_name: %s with data: %s",
                        account_id, folder_name, share_data)
        interface: InterfaceApiMailFolder = g.inter
        return interface.share_folder(account_id, folder_name, share_data)
