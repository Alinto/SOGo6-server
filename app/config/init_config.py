from __future__ import annotations
from typing import TYPE_CHECKING

from app.module.ModuleInitSogo import ModuleInitSogo
from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.utils.exceptions import AggravatedException
from app.utils import constants as cs

from .settings.ProcessSetting import process_config

if TYPE_CHECKING:
    from app.manager.cache.ClientRedis import ClientRedis


def check_basic_config() -> bool:
    """
    Check if SOGo is already configured with a system config and default domain settings

    :return: True if SOGo has a config
    :rtype: bool
    """
    config_module = ModuleAdminConfig(process_config)
    system_settings = config_module.get_system_settings()
    default_domain_settings = config_module.get_default_domain_settings()

    if system_settings and default_domain_settings:
        return True
    return False

def init_sogo() -> tuple[int, ClientRedis]:
    """
    Init sogo application
    return True if sogo is ok and already configured, False instead
    raies errort if the initializaton has problems
    """
    sogo_state = 0

    init_module = ModuleInitSogo(process_config)
    init_module.check_sogo_database()

    cache_client = init_module.check_redis()

    #TODO
    #check agent

    if init_module.errors:
        raise AggravatedException(f"Sogo cannot be initiated because: {init_module.errors}")

    sogo_state = cs.SOGO_NOT_INIT

    #No errors, check if SOGo already has a configuration
    if check_basic_config():
        sogo_state = cs.SOGO_OK

    return sogo_state, cache_client

def init_get_system_and_default_settings() -> tuple[dict, dict]:
    """
    Return the sysem and default domain settings

    :return: (system_settings, default_dimain_settings)
    :rtype: tuple[dict, dict]
    """
    config_module = ModuleAdminConfig(process_config)
    return config_module.get_both_system_and_default_domain_settings()
