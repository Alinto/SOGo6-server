from flask_smorest import Blueprint

from .ApiAdmin import blp as admin_api_blueprint
from .ApiAdminConfig import blp as amdin_config_api_blueprint

admin_apis : list[Blueprint] = [admin_api_blueprint, amdin_config_api_blueprint]
