"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines all the endpoints concerning User Mail Account(s).
All SOGo users have a default mail account (id=0) but they can add external mail accounts.
"""

from __future__ import annotations
from flask import request, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from app.utils.exceptions import RequestException
from app.utils.logger.logger import logger_api
from .schemas.mailList import MailMessageListSchema
from .interface.MailListInterface import MailListInterface



blp = Blueprint("MailList", __name__, url_prefix="/Mail/<int:account_id>/<int:folder_id>")

@blp.route("/")
class ApiMailList(MethodView):
    """
    API to list mails in a folder.
    Endpoint: /api/Mail/<account_id>/<folder_id>
    """

    @blp.response(200, MailMessageListSchema(many=True))
    def get(self, account_id: int, folder_id: int) -> list[dict]:
        """
        Return the list of mails in a specific folder.

        This endpoint returns all mails in the specified folder. If the folder does not
        exist, a 404 error is returned. In case of an unexpected error, a 500 error is returned.

        Args:
            folder_id (int): The id of the folder to fetch the mail list from.

        Returns:
            list: A list containing the mail dicts, formatted according to the MailMessageListSchema.
        """
        interface: MailListInterface = MailListInterface()
        try:
            mail_list = interface.get_mail_list(account_id, folder_id)
            if not mail_list:
                logger_api.error("Requested folder not found: %s", folder_id)
                abort(404, message="Requested folder not found.")
            return mail_list
        except RequestException as e:
            logger_api.error("Request error on mail list: %s", e)
            abort(400, message=f"Request error: {e}") #TODO: handle specific exceptions if needed
