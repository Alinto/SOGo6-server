from flask_smorest import Blueprint


from.ApiMailDetail import blp as mail_detail_blueprint
from.ApiMailFolder import blp as mail_folder_blueprint
from.ApiMailAccount import blp as mail_account_blueprint


mail_apis : list[Blueprint] = [mail_account_blueprint, mail_detail_blueprint, mail_folder_blueprint]
