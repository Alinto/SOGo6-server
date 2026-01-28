from flask_smorest import Blueprint

from .ApiUserProfile import blp as user_profile_api

user_profile_apis : list[Blueprint] = [user_profile_api]