from flask_smorest import Blueprint

from .ApiCalendarEvents import blp as calendar_events_blueprint

calendar_apis: list[Blueprint] = [calendar_events_blueprint]
