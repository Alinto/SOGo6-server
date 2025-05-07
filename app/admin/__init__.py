from flask_smorest import Blueprint

from .ApiAdmin import blp as admin_api_blueprint

admin_apis : list[Blueprint] = [admin_api_blueprint]
