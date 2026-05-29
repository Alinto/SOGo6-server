from flask_smorest import Blueprint

from .ApiCalendar import blp as calendar_blueprint

calendar_apis: list[Blueprint] = [calendar_blueprint]
