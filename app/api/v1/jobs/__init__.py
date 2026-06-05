from flask_smorest import Blueprint

from .ApiJob import blp as job_blueprint

job_apis: list[Blueprint] = [job_blueprint]
