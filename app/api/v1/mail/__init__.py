from flask_smorest import Blueprint


from.ApiMailMail import blp as mail_detail_blueprint
from.ApiMailFolder import blp as mail_folder_blueprint
from.ApiMailAccount import blp as mail_account_blueprint
from.ApiMailIdentity import blp as mail_identity_blueprint
from.ApiMailMailbox import blp as mail_mailbox_blueprint



mail_apis : list[Blueprint] = [mail_mailbox_blueprint,mail_account_blueprint, mail_identity_blueprint, mail_folder_blueprint, mail_detail_blueprint]
