from flask_smorest import Blueprint

from app.utils import constants as cs

from .admin import admin_apis
from .auth import user_auth_apis
from .mail import mail_apis
from .preference import pref_apis

v1_basic_apis: list[Blueprint] = []
v1_basic_apis += mail_apis
v1_basic_apis += pref_apis
v1_basic_apis += user_auth_apis

v1_admin_apis: list[Blueprint] = []
v1_admin_apis += admin_apis

all_v1_apis = {
    cs.API_BASIC: v1_basic_apis,
    cs.API_ADMIN: v1_admin_apis
}
