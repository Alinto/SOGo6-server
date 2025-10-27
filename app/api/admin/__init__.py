from flask_smorest import Blueprint

from .ApiAdminConfig import blp as admin_config_api_blueprint

admin_apis : list[Blueprint] = [admin_config_api_blueprint]
