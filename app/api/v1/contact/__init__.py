from flask_smorest import Blueprint

from .ApiContact import blp as contact_blueprint

contact_apis: list[Blueprint] = [contact_blueprint]
