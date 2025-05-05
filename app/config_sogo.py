from typing import Optional
from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings


class FlaskConfig(BaseSettings):
    """
    Contains settings for flask application
    """

    DEBUG : bool = True
    LANGUAGES : list[str] = ["en", "fr", "es", "de"]


class SogoConfig(BaseSettings):
    """
    Contains all sogo relative settings
    """

    IS_DEV: Optional[bool] = False


config = SogoConfig()
