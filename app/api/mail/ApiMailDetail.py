"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines all the endpoints concerning User Mail Account(s).
All SOGo users have a default mail account (id=0) but they can add external mail accounts.
"""

from flask import request, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from app.utils.logger.logger import logger_api
from app.utils.exceptions import RequestException
from .interface.MailDetailInterface import MailDetailInterface
from .schemas.mailDetail import MailDetailSchema

blp = Blueprint("MailDetail", __name__, url_prefix="/Mail/<int:account_id>/<int:folder_id>/<int:mail_id>")

@blp.route("/")
class ApiMailDetail(MethodView):
    """
    API to fetch mail details
    endpoint: /api/Mail/<account_id>/<folder_id>/<mail_id>
    """

    @blp.response(200, MailDetailSchema())
    def get(self, account_id: int, folder_id: int, mail_id: int) -> dict:
        """
        Retrieve detailed information for a specific mail item.

        Args:
            account_id (int): The account identifier.
            folder_id (int): The folder identifier.
            mail_id (int): The unique identifier of the mail to fetch.

        Returns:
            dict: A dictionary containing the mail details, formatted according to the MailDetailSchema.
        """
        interface: MailDetailInterface = MailDetailInterface()
        try:
            mail_detail = interface.get_mail_detail(account_id, folder_id, mail_id)
            if not mail_detail:
                logger_api.error("Requested mail not found: %s", mail_id)
                abort(404, message="Requested mail not found.")

            return mail_detail
        except RequestException as e:
            logger_api.error("Request error on mail detail: %s", e)
            abort(400, message=f"Request error: {e}") #TODO: handle specific exceptions if needed
