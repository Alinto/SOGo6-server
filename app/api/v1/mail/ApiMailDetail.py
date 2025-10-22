from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint, abort

from app.interface.mail.InterfaceApiMailDetail import InterfaceApiMailDetail
from app.utils.logger.logger import logger_api
from app.utils.exceptions import RequestException
from .schemas.mailDetail import MailDetailResponseSchema
from .schemas.mailMove import MailMoveSchema

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailDetail", __name__, url_prefix="/mail")


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

    interface_api = InterfaceApiMailDetail(
        process_setting=process,
        user_conf=user_conf_test,
    )
    g.inter = interface_api


@blp.route("/<int:account_id>/folder/<folder_name>/mail/<int:mail_uid>")
class ApiMailDetail(MethodView):
    """
    API to fetch mail details.
    """

    @blp.response(200, MailDetailResponseSchema)
    def get(self, account_id: int, folder_name: str, mail_uid: int) -> ResponseReturnValue:
        """
        Retrieve detailed information about a specific mail.

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
        interface: InterfaceApiMailDetail = g.inter
        return interface.get_mail_detail(account_id, folder_name, mail_uid)

