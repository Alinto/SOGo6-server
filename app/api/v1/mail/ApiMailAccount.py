from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint, abort

from app.service import sogo_cache
from app.interface.mail.InterfaceApiMailAccount import InterfaceApiMailAccount
from app.utils.logger.logger import logger_api

from .schemas.folderList import FolderListResponseSchema
from .schemas.folderCreate import FolderCreateSchema

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailAccount", __name__, url_prefix="/account")

@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.
    """
    logger_api.debug("Calling before_request for ApiMailAccount")
    process: ProcessSetting = g.process
    system_settings: dict = g.system
    domain_settings: dict = g.default_domain
    interface_api = InterfaceApiMailAccount(process_setting=process)
    g.inter = interface_api
    sogo_cache().get("test", str)

@blp.route("/<int:account_id>/folder")
class ApiMailAccount(MethodView):
    """
    API to list and create mail folders for an account.
    """

    @blp.response(200, FolderListResponseSchema)
    def get(self, account_id: int) -> ResponseReturnValue:
        """
        Retrieve the list of mail folders for a given account.

        :param account_id: The account identifier.
        :type account_id: int
        :return: A list of folder names.
        :rtype: ResponseReturnValue
        :raises RequestException: If the account or folders cannot be found.
        """
        logger_api.debug("Calling ApiMailAccount: Fetching folder list for account_id: %s", account_id)
        interface: InterfaceApiMailAccount = g.inter
        return interface.get_folder_list(account_id)

    @blp.arguments(FolderCreateSchema, example=FolderCreateSchema.example())
    @blp.response(201)
    def post(self, folder_data: dict, account_id: int) -> ResponseReturnValue:
        """
        Create a new mail folder for a given account.

        :param folder_data: The folder data containing the name.
        :type folder_data: dict
        :param account_id: The account identifier.
        :type account_id: int
        :return: The created folder information.
        :rtype: ResponseReturnValue
        :raises RequestException: If the folder cannot be created.
        """
        logger_api.debug("Calling ApiMailAccount: Creating folder for account_id: %s with data: %s", account_id, folder_data)
        interface: InterfaceApiMailAccount = g.inter
        folder_name = folder_data.get("name")
        if not folder_name:
            abort(400, message="Missing folder name")
            return {"status": False, "errors": "Missing folder name"}
        return interface.create_folder(account_id, folder_name)
