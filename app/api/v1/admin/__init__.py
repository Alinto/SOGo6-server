from flask_smorest import Blueprint

from .ApiAdminConfig import blp as admin_config_api_blueprint
from .ApiAdminUser import blp as admin_user_api_blueprint
from .ApiAdminAuth import blp as admin_auth_api_blueprint

admin_apis : list[Blueprint] = [admin_auth_api_blueprint, admin_config_api_blueprint, admin_user_api_blueprint]
