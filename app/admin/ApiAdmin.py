from flask import request, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort


blp = Blueprint("ApiAdmin", __name__, url_prefix="/admin")


@blp.route("/")
class ApiAdmin(MethodView):
    @blp.response(200)
    def get(self):
        """Get admin value"""


        return "Admin Api"
