from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.mail.InterfaceApiMailIdentity import InterfaceApiMailIdentity
from app.utils.logger.logger import logger_api
from app.utils.api.ApiBaseResponse import ApiBaseResponse

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting

blp = Blueprint("ApiMailIdentity", __name__, url_prefix="/mailboxes/<int:account_id>/identities")


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

    interface_api = InterfaceApiMailIdentity(
        process_setting=process,
        user_conf=user_conf_test,
    )
    g.inter = interface_api


@blp.route("")
class ApiMailBoxesAccountIdentity(MethodView):
    """
    API to manage mail identities for a given mailbox. (NOT IMPLEMENTED)
    """
    def get(self, account_id: int) -> ResponseReturnValue:
        """
        Get identities for this mailbox  (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailBoxesAccountIdentity.get for account_id: %s", account_id)
        interface: InterfaceApiMailIdentity = g.inter
        return interface.get_mailbox_identities(account_id)

    def post(self, account_id: int) -> ResponseReturnValue:
        """
        Create a new identity for this mailbox  (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailBoxesAccountIdentity.post for account_id: %s", account_id)
        interface: InterfaceApiMailIdentity = g.inter
        return interface.create_mailbox_identity(account_id)


@blp.route("/<int:identity_id>")
class ApiMailIdentity(MethodView):
    """
    API to manage a specific mail identity.
    """

    @blp.response(200, ApiBaseResponse)
    def get(self, account_id: int, identity_id: int) -> ResponseReturnValue:
        """Retrieve a specific mail identity. (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailIdentity.get for account_id: %s, identity_id: %s", account_id, identity_id)
        interface: InterfaceApiMailIdentity = g.inter
        return interface.get_identity(account_id, identity_id)

    def delete(self, account_id: int, identity_id: int) -> ResponseReturnValue:
        """Delete a specific mail identity. (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailIdentity.delete for account_id: %s, identity_id: %s", account_id, identity_id)
        interface: InterfaceApiMailIdentity = g.inter
        return interface.delete_identity(account_id, identity_id)

    def patch(self, account_id: int, identity_id: int) -> ResponseReturnValue:
        """Update a specific mail identity. (NOT IMPLEMENTED)
        """
        logger_api.debug("Calling ApiMailIdentity.patch for account_id: %s, identity_id: %s", account_id, identity_id)
        interface: InterfaceApiMailIdentity = g.inter
        return interface.update_identity(account_id, identity_id)
