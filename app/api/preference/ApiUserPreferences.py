# -*- coding: utf-8 -*-
from flask import request, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from app.module.preference.model.prefs import Prefs

from .schemas.userPreferences import SaveSchema, RetGetUserPreferences



blp = Blueprint("UsersPreferences", __name__, url_prefix="/Preferences")

@blp.before_request
def _init_user_prefs():

    # if 'user' not in g:
    #     abort(400, "No user found")

    user_id = "test@blabla.com"
    pref = Prefs()
    pref.init_with_user_id(user_id)
    g.pref = pref


@blp.route("/")
class ApiUserPreferences(MethodView):
    @blp.response(200, RetGetUserPreferences())
    def get(self):
        """Get user prefs"""

        pref : Prefs = g.pref
        ret = pref.get_defaults_for_domain("blabla")
        print(ret)
        schema = RetGetUserPreferences()
        ret = schema.dump(ret)
        print(ret)
        return ret
        #return ret

    @blp.arguments(SaveSchema)
    @blp.response(200)
    def post(self, new_data):
        """Save Users Preferences"""
        print(f"Save")
        return