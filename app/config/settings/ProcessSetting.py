from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.exceptions import BugException

# Path to the process configuration file (key=value format).
# Environment variables always take precedence over values defined in this file.
PROCESS_CONF_PATH = "/etc/sogo/process.conf"


class FlaskConfig(BaseSettings):
    """
    Contains settings for Flask application
    """

    model_config = SettingsConfigDict(
        env_file=PROCESS_CONF_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    SOGO_INIT_SYSTEM_SETTINGS_PATH: str = ""
    SOGO_INIT_DOMAIN_SETTINGS_PATH: str = ""
    # Public-facing base URL (scheme + host[:port]) used to build absolute capability URLs
    # served to external clients. Required behind a reverse proxy, where the host seen by Flask
    # differs from the public one. Empty: fall back to Flask's own external URL.
    SOGO_P_PUBLIC_BASE_URL: str = ""

    # Agent (Celery) — broker and result backend reuse SOGO_P_REDIS_URL. Only the
    # process-wide settings are exposed here. Per-task settings (soft / hard timeout,
    # retry policy) belong to each Task subclass and are set at task definition time.
    # Defaults are tuned for the dev container; production overrides via env vars.

    # Number of worker processes spawned by `poetry run agent`. ~1 per CPU is a sensible
    # ceiling for IO-bound tasks; raise it for CPU-bound parsing.
    SOGO_P_AGENT_WORKER_CONCURRENCY: int = 4
    # Redis visibility timeout: a reserved message is redelivered if the worker hasn't acked
    # within this delay. Must exceed the longest task we run, otherwise we get phantom
    # double executions when Redis re-queues an in-flight task.
    SOGO_P_AGENT_BROKER_VISIBILITY_TIMEOUT_SECONDS: int = 6 * 3600
    # Messages prefetched per worker. 1 keeps long tasks isolated; raise it only for very
    # short tasks where the broker round-trip dominates.
    SOGO_P_AGENT_WORKER_PREFETCH_MULTIPLIER: int = 1
    # How long a TaskState lingers in Redis after the task is completed (post-mortem window).
    SOGO_P_AGENT_TASK_STATE_TTL_SECONDS: int = 3 * 24 * 3600
    # Filesystem path used by the Beat scheduler for its state file. Must be writable by
    # the application user. The dev container provisions ``/var/celery`` in its Dockerfile;
    # in production the path should sit on a persistent volume so state survives restarts.
    SOGO_P_AGENT_BEAT_SCHEDULE_PATH: str = "/var/celery/sogo-agent-beat-schedule"
    # Directory for transient files (ICS exports, attachments, agent task outputs, etc.).
    # When the agent runs in multiple instances (workers spread across hosts or containers)
    # and TASK_RESULT_LARGE_STORAGE is FILE, this path must point to a shared volume
    # mounted on every agent instance and on the Flask API process. Otherwise a result
    # written by one worker is unreachable from the API or from another worker.
    SOGO_P_TMP_PATH: str = "/tmp"

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
