from typing import Any
from pydantic_settings import BaseSettings

from app.utils.exceptions import BugException

class FlaskConfig(BaseSettings):
    """
    Contains settings for Flask application
    """

    #Flask
    ######

    #Set you own secret key for production
    SECRET_KEY: str = "90777fd15f122afad7f16f65895feaec5394b053847cb8beab51a7969b2ac75c"


    #Flask smorest
    ##############

    #Serve the swagger
    DO_SWAGGER: bool = True

    #Flask smorest config for ui api
    BASIC_API_TITLE: str               = "SOGo API"
    BASIC_API_VERSION: str             = "v1"
    BASIC_OPENAPI_VERSION: str         = "3.0.2"
    BASIC_OPENAPI_URL_PREFIX: str      = "/"
    BASIC_OPENAPI_JSON_PATH: str       = "openapi-basic.json"
    BASIC_OPENAPI_SWAGGER_UI_PATH: str = "/swagger-basic"
    BASIC_OPENAPI_SWAGGER_UI_URL: str  = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    BASIC_API_SPEC_OPTIONS: dict = {'security': [{"bearerAuth": []}], 'components': {
            "securitySchemes":
                {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT"
                    }
                }
        }}


    #Flask smorest config for admin api
    ADMIN_API_TITLE: str               = "Sogo Admin API"
    ADMIN_API_VERSION: str             = "v1"
    ADMIN_OPENAPI_VERSION: str         = "3.0.2"
    ADMIN_OPENAPI_URL_PREFIX: str      = "/"
    ADMIN_OPENAPI_JSON_PATH: str       = "openapi-admin.json"
    ADMIN_OPENAPI_SWAGGER_UI_PATH: str = "/swagger-admin"
    ADMIN_OPENAPI_SWAGGER_UI_URL: str  = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    ADMIN_API_SPEC_OPTIONS: dict = {'security': [{"bearerAuth": []}], 'components': {
            "securitySchemes":
                {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT"
                    }
                }
        }}



class ProcessSetting(FlaskConfig):
    """
    Contains all SOGo relative settings
    """
    SOGO_P_REDIS_URL: str = "redis://redis:6379"
    SOGO_P_REDIS_RESP_3: bool = True # Version of RESP, 3 is strongly recommanded

    SOGO_P_SECRET: str
    SOGO_P_VOUCHER_SECRET: str #Fernet key must be 32 char string in utf-8.
    SOGO_AES_ENC_KEY: str #32 bytes key for AES-256

    SOGO_P_DB_TYPE: str = "PostgreSQL"
    SOGO_P_DB_USER: str = "admin"     #TODO test all that...
    SOGO_P_DB_PASS: str = "admin"
    SOGO_P_DB_HOST: str = "localhost"
    SOGO_P_DB_PORT: int = 5432
    SOGO_P_DB_SSL: bool = False
    SOGO_P_DB_ENC: str  = "utf8" #encoding, needed or autodetected ?

    SOGO_LOG_PATH: str = "/var/log/sogo/sogo.log"

    def __getitem__(self, i:str) -> Any:
        if hasattr(self, i):
            return getattr(self, i)
        raise BugException(f"Try to get a process settings that does not exist: {i}")


    def get_db_settings(self) -> dict:
        """
        Return all related db settings (prefix is SOGO_P_DB)
        """
        db_dict = {
            "db_user": self.SOGO_P_DB_USER,
            "db_pwd":  self.SOGO_P_DB_PASS,
            "db_host": self.SOGO_P_DB_HOST,
            "db_port": self.SOGO_P_DB_PORT,
            "db_ssl":  self.SOGO_P_DB_SSL,
            "db_enc":  self.SOGO_P_DB_ENC
        }
        return db_dict

    def get_redis_settings(self) -> dict:
        """
        Get a dict ready to be passed as kwargs to instantiate ClientRedis

        {
            "url_str": SOGO_P_REDIS_URL,
            "resp3": SOGO_P_REDIS_RESP_3
        }

        :return: Dict with the correct name and value
        :rtype: dict
        """
        redis_dict = {
            "url_str": self.SOGO_P_REDIS_URL,
            "resp3": self.SOGO_P_REDIS_RESP_3
        }
        return redis_dict


process_config = ProcessSetting() # type: ignore [call-arg]
