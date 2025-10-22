from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint, abort

from app.interface.mail.InterfaceApiMailAccount import InterfaceApiMailAccount
from app.utils.logger.logger import logger_api
from app.utils.api.ApiResponse import ApiBaseResponse
from app.utils.exceptions import RequestException

from .schemas.folderList import FolderListResponseSchema
from .schemas.folderCreate import FolderCreateSchema

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailAccount", __name__, url_prefix="/mail")

@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.

    This reads IMAP server and port from g.default_domain if present (domain settings),
    falling back to the previous defaults otherwise.
    """
    logger_api.debug("Calling before_request for ApiMailAccount")
    process: ProcessSetting = g.process
    system_settings: dict = g.system
    domain_settings: dict = g.default_domain  # peut être None ou un dict
    imap_server = None
    imap_port = None
    if isinstance(domain_settings, dict):
        mail_settings = domain_settings.get("MAIL_SETTINGS", {})
        print("mail_settings =", mail_settings)
        if isinstance(mail_settings, dict):
            imap_server = mail_settings.get("SOGO_D_IMAP_SERVER")
            imap_port = mail_settings.get("SOGO_D_IMAP_PORT")

    # Liste de configurations IMAP : index 0 = compte principal, index 1 = compte secondaire. A remplacer par un futur User?
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

    interface_api = InterfaceApiMailAccount(
        process_setting=process,
        user_conf=user_conf_test,
    )
    g.inter = interface_api

@blp.route("/<int:account_id>/folder")
class ApiMailAccount(MethodView):
    """
    API to list and create mail folders for an account.
    """

    @blp.response(200, FolderListResponseSchema)
    def get(self, account_id: int) -> ResponseReturnValue:
        """
        Retrieve the list of mail folders for a given account.

        :param account_id: The account identifier (0 = primary, 1 = secondary).
        :type account_id: int
        :return: A list of folder names.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailAccount: Fetching folder list for account_id: %s", account_id)
        interface: InterfaceApiMailAccount = g.inter
        try:
            return interface.get_folder_list(account_id)
        except RequestException as e:
            logger_api.error("RequestException in get_folder_list: %s", e)
            abort(400, message=str(e))


    @blp.arguments(FolderCreateSchema, example=FolderCreateSchema.example())
    @blp.response(201, ApiBaseResponse)
    def post(self, folder_data: dict, account_id: int) -> ResponseReturnValue:
        """
        Create a new mail folder for a given account.

        :param folder_data: The folder data containing the name.
        :type folder_data: dict
        :param account_id: The account identifier (0 = primary, 1 = secondary).
        :type account_id: int
        :return: The created folder information.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("Calling ApiMailAccount: Creating folder for account_id: %s with data: %s", account_id, folder_data)
        interface: InterfaceApiMailAccount = g.inter
        folder_name = folder_data.get("name")
        if not folder_name:
            abort(400, message="Missing folder name")
            return {"status": False, "errors": "Missing folder name", "data": {}}
        try:
            return interface.create_folder(account_id, folder_name)
        except RequestException as e:
            logger_api.error("RequestException in create_folder: %s", e)
            abort(400, message=str(e))
