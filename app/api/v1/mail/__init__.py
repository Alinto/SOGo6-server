from flask_smorest import Blueprint


from.ApiMailMail import blp as mail_detail_blueprint
from.ApiMailSend import blp as mail_send_blueprint
from.ApiMailFolder import blp as mail_folder_blueprint
from.ApiMailMailbox import blp as mail_mailbox_blueprint
from.ApiMailFilter import blp as mail_filter_blueprint


mail_apis : list[Blueprint] = [mail_mailbox_blueprint, mail_send_blueprint, mail_folder_blueprint, mail_detail_blueprint, mail_filter_blueprint]
