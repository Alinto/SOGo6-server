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
    FolderSharePatchSchema,
    FolderSharePutSchema,
    FolderSharePostSchema,
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
    """API to manage sharing of a specific mail folder and its users' permissions.

    Rights can be expressed two ways in the request body, and at least one of them must be
    provided for each user entry:

    - ``permissions``: a simplified list of IMAP ACL codes to grant, e.g. ``["l", "r"]``.
      Any code not listed is considered not granted.
    - ``rights``: an advanced object with one explicit 0/1 flag per right, e.g.
      ``{"user_can_view_folder": 1, "user_can_read_mails": 1}``.

    Correspondence between simplified codes and advanced rights (see
    ``FOLDER_PERMISSION_CODE_TO_RIGHT`` in ``app/api/v1/mail/schemas/folder.py``):

    | Code IMAP | Droit avancé |
    |---|---|
    | l | user_can_view_folder (Voir le dossier) |
    | r | user_can_read_mails (Lire les mails) |
    | s | user_can_mark_mails_read (Marquer comme lu/non lu) |
    | w | user_can_write_mails (Modifier les indicateurs des mails) |
    | i | user_can_insert_mails (Insérer, copier des mails) |
    | p | user_can_post_mails (Envoyer des mails) |
    | k | user_can_create_subfolders (Créer des sous-dossiers) |
    | x | user_can_remove_folder (Supprimer le dossier) |
    | t | user_can_erase_mails (Effacer les mails) |
    | e | user_can_expunge_folder (Purger le dossier) |
    | a | user_is_administrator (Administrer les droits du dossier) |

    If both ``permissions`` and ``rights`` are provided for the same entry, they must agree on
    every right they both cover. Otherwise the API answers ``400 S001103``
    (``ERROR_SHARE_PERMISSIONS_RIGHTS_MISMATCH``).

    Each entry also requires ``user_class`` (``"user"`` or ``"anyone"``); ``c_email`` and ``uid``
    are required when ``user_class`` is ``"user"``.
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

    @blp.arguments(FolderSharePatchSchema(many=True), example=FolderSharePatchSchema.example(), error_status_code=400)  # type: ignore [arg-type]
    @blp.response(200, FolderShareResponseSchema, example=FolderShareResponseSchema.example())
    def patch(self, share_data: list, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Partially update sharing rights for the specified folder.

        Only the users specified in the request body are modified. Other existing shares
        remain unchanged. See the resource docstring for the ``permissions``/``rights`` format.

        :param share_data: List of users with their rights configuration
        :type share_data: list
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: ApiBaseResponse with share result
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderIdShare.patch for account_id: %s, folder_name: %s with data: %s",
                        account_id, folder_name, share_data)
        interface: InterfaceApiMailFolder = g.inter
        return interface.patch_folder_share(account_id, folder_name, share_data)

    @blp.arguments(FolderSharePutSchema(many=True), example=FolderSharePutSchema.example(), error_status_code=400)  # type: ignore [arg-type]
    @blp.response(200, FolderShareResponseSchema, example=FolderShareResponseSchema.example())
    def put(self, share_data: list, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Replace all sharing rights for the specified folder.

        All existing shares are replaced by the users specified in the request body.
        See the resource docstring for the ``permissions``/``rights`` format.

        :param share_data: List of users with their rights configuration
        :type share_data: list
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: ApiBaseResponse with share result
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailFolderIdShare.put for account_id: %s, folder_name: %s with data: %s",
                        account_id, folder_name, share_data)
        interface: InterfaceApiMailFolder = g.inter
        return interface.put_folder_share(account_id, folder_name, share_data)

    @blp.arguments(FolderSharePostSchema(many=True), example=FolderSharePostSchema.example(), error_status_code=400)  # type: ignore [arg-type]
    @blp.response(200, FolderShareResponseSchema, example=FolderShareResponseSchema.example())
    def post(self, share_data: list, account_id: str, folder_name: str) -> ResponseReturnValue:
        """Grant sharing rights on the specified folder to one or several users.

        Adds or updates ACL permissions on the folder for the specified users, in addition to
        any existing share. See the resource docstring for the ``permissions``/``rights`` format.

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
        return interface.post_folder_share(account_id, folder_name, share_data)
