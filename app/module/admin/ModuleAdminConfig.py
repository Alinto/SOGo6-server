from __future__ import annotations
from typing import TYPE_CHECKING

from app.config.db.tables import TABLE_SETTINGS, TABLE_RULES, TABLE_DOMAIN, COL_SETTINGS_SYSTEM
from app.utils.module.importManager import import_and_instantiate_manager

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL

class ModuleAdminConfig:
    """
    Module to handle systems, domains and rules settings
    """
    def __init__(self, process_settings: ProcessSetting):
        """
        """
        self.process_settings  = process_settings
        fake_process_settings_db = "PostgreSQL"
        sogo_db_type = f"Client{fake_process_settings_db}"

        self.sogo_db_manager: ClientSQL = import_and_instantiate_manager(module_path="app.manager.db",
                                                         module_and_class_name=sogo_db_type,
                                                         module_args=self.process_settings.get_db_settings())
    
    def update_system_settings(self, new_param: dict) -> bool:

        self.sogo_db_manager.connect()

        #Get the current system settings
        self.sogo_db_manager.select_from_table(table_name=TABLE_SETTINGS.name,
                                               column_tuple=(COL_SETTINGS_SYSTEM.name,),
                                               condition="id = 1")
        #Merge the new data and check it

        #Update the column

        return True

