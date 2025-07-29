from .settings.ProcessSetting import config
from app.manager.ClientSQL import CLientSQL

class ConfigSystemDomain():
    """
    Class that manages systems and domains configuration
    """

    def __init__(self):
        """
        Fetch process settings for database
        """
        db_config = {
            "db_user": config["SOGO_P_DB_USER"],
            "db_pwd":  config["SOGO_P_DB_PASS"],
            "db_host": config["SOGO_P_DB_HOST"],
            "db_port": config["SOGO_P_DB_PORT"],
            "db_ssl":  config["SOGO_P_DB_SSL"],
            "db_enc":  config["SOGO_P_DB_ENC"]
        }
        db_client = CLientSQL(**db_config)


    def init_without_domain(self):
        """
        Fetch all systems settings
        """

    def init_with_domain(self, domain: str):
        """
        Fetch all systems and domains setting
        """

    def is_sogo_configured(self) -> bool:
        """
        Return True is SOGo has been configured and is functionnal
        return False if this is not the case
        """
