from flask_smorest import Blueprint

from .ApiUserPreferences import blp as user_preference_api
from .ApiUserProfile import blp as user_profile_api
from .ApiUserShare import blp as user_share_api

user_profile_apis : list[Blueprint] = [user_profile_api, user_preference_api, user_share_api]
