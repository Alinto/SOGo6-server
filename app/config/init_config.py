from app.module.ModuleInitSogo import ModuleInitSogo
from app.utils.exceptions import AggravatedException

from .settings.ProcessSetting import process_config


def init_sogo() -> bool:
    """
    Init sogo application
    return True if sogo is ok and already configured, False instead
    raies errort if the initializaton has problems
    """
    init_module = ModuleInitSogo(process_config)
    init_module.check_sogo_database()

    # if not init_module.init_ok:
    if init_module.errors:
        raise AggravatedException(f"Sogo cannot be initiated because: {init_module.errors}")
        # raise AggravatedException("Sogo cannot be initiated, looks the logs for more info")
    
    return True

