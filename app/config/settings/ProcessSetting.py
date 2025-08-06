from typing import Optional
from pydantic_settings import BaseSettings


class FlaskConfig(BaseSettings):
    """
    Contains settings for Flask application
    """

    #Flask
    ######
    
    #Set you own secret key for production
    SECRET_KEY: Optional[str] = "90777fd15f122afad7f16f65895feaec5394b053847cb8beab51a7969b2ac75c"


    #Flask smorest
    ##############

    #Serve the swagger
    DO_SWAGGER: bool = True

    #Flask smorest config for ui api
    UI_API_TITLE: str               = "My UI API"
    UI_API_VERSION: str             = "v1"
    UI_OPENAPI_VERSION: str         = "3.0.2"
    UI_OPENAPI_URL_PREFIX: str      = "/"
    UI_OPENAPI_JSON_PATH: str       = "openapi-ui.json"
    UI_OPENAPI_SWAGGER_UI_PATH: str = "/swagger-ui"
    UI_OPENAPI_SWAGGER_UI_URL: str  = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    #Flask smorest config for admin api
    ADMIN_API_TITLE: str               = "My Admin API"
    ADMIN_API_VERSION: str             = "v1"
    ADMIN_OPENAPI_VERSION: str         = "3.0.2"
    ADMIN_OPENAPI_URL_PREFIX: str      = "/"
    ADMIN_OPENAPI_JSON_PATH: str       = "openapi-admin.json"
    ADMIN_OPENAPI_SWAGGER_UI_PATH: str = "/swagger-admin"
    ADMIN_OPENAPI_SWAGGER_UI_URL: str  = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"



class ProcessSetting(FlaskConfig):
    """
    Contains all SOGo relative settings
    """
    SOGO_P_REDIS_URL: str = "redis://redis:6379"
    SOGO_P_REDIS_TTL: int = "300" # Time to live of cached key. See https://redis.io/docs/latest/commands/ttl/

    SOGO_P_SECRET: str = "secret_is_a_32_characters_string" #TODO no default value and set length -> https://docs.pydantic.dev/latest/concepts/pydantic_settings/#usage

    SOGO_P_DB_USER: str = "admin"     #TODO test all that...
    SOGO_P_DB_PASS: str = "admin"
    SOGO_P_DB_HOST: str = "localhost"
    SOGO_P_DB_PORT: int = 5432
    SOGO_P_DB_SSL: bool = False  #Check with sqlalchemy if this is needed or autodetected
    SOGO_P_DB_ENC: str  = "utf8" #encoding, needed or autodetected ?

    SOGO_LOG_PATH: str = "/var/log/sogo/sogo.log"

    def get_db_settings(self) -> dict:
        """
        Return all related db settings (prefix is SOGO_P_DB)
        """
        process_settings_dict : dict[str,str] = self.model_dump()
        db_dict = {
            "db_user": self.SOGO_P_DB_USER,
            "db_pwd":  self.SOGO_P_DB_PASS,
            "db_host": self.SOGO_P_DB_HOST,
            "db_port": self.SOGO_P_DB_PORT,
            "db_ssl":  self.SOGO_P_DB_SSL,
            "db_enc":  self.SOGO_P_DB_ENC
        }
        return db_dict


process_config = ProcessSetting()
print(f"Process_setting = {process_config.model_dump()}")