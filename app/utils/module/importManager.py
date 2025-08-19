from __future__ import annotations
from typing import Any

from importlib import import_module

from app.utils.logger.logger import logger
from app.utils.exceptions import AggravatedException

def import_and_instantiate_manager(module_path: str, module_and_class_name: str, module_args: dict) -> Any:
    """
    Utils function for modules to instantiate the correct manager

    :param module_path: Python path of the module (ex: app.manager.db)
    :type module_path: str
    :param module_and_class_name: Name of the module and the class (ex: ClientPostgreSQL).
    If the naming rule were corretly followed, the module has the same has its main class.
    :type module_and_class_name: str
    :param module_args: Dictionnary used to instiate the class
    :type module_args: dict
    :raises AggravatedException: Manager has failed to get or instantiate
    :return: The manager object, ready to use.
    :rtype: Any
    """
    try:
        sogo_manager_module     = import_module(f"{module_path}.{module_and_class_name}")
        sogo_manager_class      = getattr(sogo_manager_module, module_and_class_name)
        sogo_manager  = sogo_manager_class(**module_args)
    except (ModuleNotFoundError, NameError, TypeError) as e:
        logger.error("Cannot instantiate sogo database manager, config or package problem: %s", e)
        raise AggravatedException("Cannot instantiate sogo database") from e
    except Exception as e:
        logger.error("Cannot instantiate sogo database manager, unexpecte error: %s", e)
        raise AggravatedException("Cannot instantiate sogo database") from e

    return sogo_manager
