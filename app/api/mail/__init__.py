from flask_smorest import Blueprint

from .ApiMailAccount import blp as mail_account_blueprint
from .ApiMailDetail import blp as mail_detail_blueprint
from .ApiMailList import blp as mail_list_blueprint

mail_apis : list[Blueprint] = [mail_account_blueprint, mail_detail_blueprint, mail_list_blueprint]
