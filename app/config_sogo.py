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



class SogoConfig(FlaskConfig):
    """
    Contains all SOGo relative settings
    """
    SOGO_P_REDIS_URL: str = "redis://redis:6379"
    SOGO_P_REDIS_TTL: int = "300" # Time to live of cached key. See https://redis.io/docs/latest/commands/ttl/

    SOGO_P_SECRET: str = "secret_is_a_32_characters_string" #TODO no default value and set length -> https://docs.pydantic.dev/latest/concepts/pydantic_settings/#usage



config = SogoConfig()
