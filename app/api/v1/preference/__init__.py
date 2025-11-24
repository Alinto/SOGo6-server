from flask_smorest import Blueprint

from .ApiUserPreferences import blp as user_pref_blueprint

pref_apis : list[Blueprint] = [user_pref_blueprint]
