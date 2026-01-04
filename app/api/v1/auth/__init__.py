from flask_smorest import Blueprint

from .AuthUserApi import blp as user_auth_api

user_auth_apis : list[Blueprint] = [user_auth_api]
