from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailMailbox import InterfaceApiMailMailbox
from app.utils.logger.logger import logger_api
from app.utils.api.ApiBaseResponse import ApiBaseResponse

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailMailbox", __name__, url_prefix="/mailboxes")


@blp.before_request
def init_mail_config() -> None:
    """
    Initialize the mail interface and any other required configuration for the request.

    This reads IMAP server and port from g.default_domain if present (domain settings),
    falling back to the previous defaults otherwise.
    """
    logger_api.debug("Calling before_request for ApiMailAccount")
    process: ProcessSetting = g.process
    system_settings: dict = g.system
    domain_settings: dict = g.default_domain  # peut être None ou un dict
    if isinstance(domain_settings, dict):
        mail_settings = domain_settings.get("MAIL_SETTINGS", {})
        print("mail_settings =", mail_settings)
        if isinstance(mail_settings, dict):
            imap_server = mail_settings.get("SOGO_D_IMAP_SERVER")
            imap_port = mail_settings.get("SOGO_D_IMAP_PORT")
            imap_type = mail_settings.get("SOGO_D_MAIL_SERVER_TYPE")

    # Liste de configurations IMAP : index 0 = compte principal, index 1 = compte secondaire. A remplacer par un futur User?
    user_conf_test = [
        {
            "username": "tkeriven@snapshot.alinto.org",
            "password": "Banane2!",
            "type": "imap",
            "server": "192.168.69.31",
            "port": 10143
        },
        {
            "username": "tkeriven3@snapshot.alinto.org",
            "password": "Banane01!",
            "type": "imap",
            "server": "192.168.69.31",
            "port": 10143
        }
    ]

    interface_api = InterfaceApiMailMailbox(
        process_setting=process,
        user_conf=user_conf_test,
    )
    g.inter = interface_api


@blp.route("")
class ApiMailBoxes(MethodView):
    """
    API to manage mailboxes.
    """

    @blp.response(200, ApiBaseResponse)
    def get(self) -> ResponseReturnValue:
        """
        List all configured mailboxes (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailBoxes.get to list all mailboxes")
        interface: InterfaceApiMailMailbox = g.inter
        return interface.list_mailboxes()

    @blp.response(201, ApiBaseResponse)
    def post(self) -> ResponseReturnValue:
        """
        Create a new mailbox (add external account) (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailBoxes.post to create a new mailbox")
        interface: InterfaceApiMailMailbox = g.inter
        return interface.create_mailbox()


@blp.route("/<int:account_id>")
class ApiMailBoxesAccount(MethodView):
    """
    Resource: Mailbox by ID
    """
    def patch(self, account_id: int) -> ResponseReturnValue:
        """
        Update mailbox settings (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailBoxesAccount.patch for account_id: %s", account_id)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.update_mailbox(account_id)

    def delete(self, account_id: int) -> ResponseReturnValue:
        """
        Delete a mailbox (only external accounts) (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailBoxesAccount.delete for account_id: %s", account_id)
        interface: InterfaceApiMailMailbox = g.inter
        return interface.delete_mailbox(account_id)
