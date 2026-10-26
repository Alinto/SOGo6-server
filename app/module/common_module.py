#Here are the methods commonly used among modules
from __future__ import annotations
from typing import TYPE_CHECKING

from app.manager.db import _MAPPING_DB
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL


def get_sogo6_database(process_settings: ProcessSetting) -> ClientSQL:
    """
    Instantiate and return the manager for SOGo 6 database

    :param type_db: Type of the database cae-unsensitive "postgresql", "mysql"
    :type type_db: str
    :param process_settings: _description_
    :type process_settings: ProcessSetting
    :return: _description_
    :rtype: ClientSQL
    """
    sogo_db_type = _MAPPING_DB[process_settings.SOGO_P_DB_TYPE.lower()]
    sogo_db_manager: ClientSQL = import_and_instantiate_manager(module_path="app.manager.db",
                                                             module_and_class_name=sogo_db_type,
                                                             module_args=process_settings.get_db_settings())
    return sogo_db_manager
