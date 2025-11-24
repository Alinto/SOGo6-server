from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint, abort

from app.interface.mail.InterfaceApiMailDetail import InterfaceApiMailDetail
from app.utils.logger.logger import logger_api
from .schemas.mailDetail import MailDetailResponseSchema
from .schemas.mailMove import MailMoveSchema

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailDetail", __name__, url_prefix="/account")

@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.
    """
    logger_api.debug("Calling before_request for ApiMailDetail")
    process: ProcessSetting = g.process
    interface_api = InterfaceApiMailDetail()
    g.inter = interface_api

@blp.route("/<int:account_id>/folder/<folder_id>/mail/<int:mail_id>")
class ApiMailDetail(MethodView):
    """
    API to fetch mail details.
    """

    @blp.response(200, MailDetailResponseSchema)
    def get(self, account_id: int, folder_id: str, mail_id: int) -> ResponseReturnValue:
        """
        Retrieve detailed information about a specific mail.

        :param account_id: The account identifier.
        :type account_id: int
        :param folder_id: The folder identifier.
        :type folder_id: str
        :param mail_id: The unique identifier of the mail.
        :type mail_id: int
        :return: Detailed mail information.
        :rtype: ResponseReturnValue
        :raises RequestException: If the mail or folder cannot be found.
        """
        logger_api.debug("Calling ApiMailDetail: Fetching mail detail for account_id: %s, folder_id: %s, mail_id: %s", account_id, folder_id, mail_id)
        interface: InterfaceApiMailDetail = g.inter
        return interface.get_mail_detail(account_id, folder_id, mail_id)
