from flask_smorest import Blueprint

from app.utils import cs_api

from .admin import admin_apis
from .mail import mail_apis
from .preference import pref_apis

v1_basic_apis: list[Blueprint] = []
v1_basic_apis += mail_apis
v1_basic_apis += pref_apis

v1_admin_apis: list[Blueprint] = []
v1_admin_apis += admin_apis

all_v1_apis = {
    cs_api.API_BASIC: v1_basic_apis,
    cs_api.API_ADMIN: v1_admin_apis
}
