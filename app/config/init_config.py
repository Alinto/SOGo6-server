from app.module.ModuleInitSogo import ModuleInitSogo
from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.utils.exceptions import AggravatedException

from .settings.ProcessSetting import process_config


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

def init_sogo() -> int:
    """
    Init sogo application
    return True if sogo is ok and already configured, False instead
    raies errort if the initializaton has problems
    """
    sogo_state = 0

    init_module = ModuleInitSogo(process_config)
    init_module.check_sogo_database()

    #TODO
    #check_redis
    #check agent

    if init_module.errors:
        raise AggravatedException(f"Sogo cannot be initiated because: {init_module.errors}")

    sogo_state = 1

    #No errors, check if SOGo already has a configuration
    if check_basic_config():
        sogo_state = 2

    
    return sogo_state

def init_get_system_and_default_settings() -> tuple:
    """
    Return the sysem and default domain settings

    :return: (system_settings, default_dimain_settings)
    :rtype: tuple[dict, dict]
    """
    config_module = ModuleAdminConfig(process_config)
    return config_module.get_both_system_and_default_domain_settings()
