# -*- coding: utf-8 -*-

"""
This file is part of SOGo 6 software https://github.com/Alinto/SOGo6-server

This file defines all the endpoints concernning User Mail Folder of their Account
"""


from flask import request, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .schemas.mailAccounts import ListMailAccountsResponse, \
                                  ListMailAccountsDelegation


blp = Blueprint("MailAccount", __name__, url_prefix="/Mail/<account_id>")


@blp.route("/")
class ApiMailAccount(MethodView):
    """
    API to list user's mail folder
    endpont: /api/Mail/<account_id>
    """

    @blp.response(200, ListMailAccountsResponse())
    def get(self):
        """
        Return the list of account of the user
        """
        item1 = {
            "name": "default",
            "mail": "dude@test.com",
            "id": 0
        }
        item2 = {
            "name": "work",
            "mail": "hewill@test.com",
            "id": 1
        }

        list_items = {"accounts": [item1, item2]}
        return list_items

@blp.route("/Delegate")
class ApiMailAccountDelegate(MethodView):
    """
    API to list user's mail accounts
    endpoint: GET/POST /api/Mail/0/Delegate

    Only works for the default account which id is 0.
    """

    @blp.response(200, ListMailAccountsDelegation())
    def get(self):
        """
        Return the list of accounts that have delegation's right
        """

        list_items = {"accounts": ["dude@test.com", "hewill@test.com"]}
        return list_items

    @blp.arguments(ListMailAccountsDelegation())
    @blp.response(200)
    def post(self, data):
        """
        Save the accounts with delegation right
        """
        print(data)

        return 