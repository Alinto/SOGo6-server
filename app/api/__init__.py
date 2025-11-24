from flask_smorest import Blueprint

from .v1 import all_v1_apis

all_apis = {
    "v1": all_v1_apis
}
