from flask_smorest import Blueprint

from .ApiMailAccount import blp as mail_account_blueprint

mail_apis : list[Blueprint] = [mail_account_blueprint]
