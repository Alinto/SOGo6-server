from __future__ import annotations
from typing import TYPE_CHECKING, Any

from marshmallow.exceptions import ValidationError

from app.config.db.tables import TABLE_SETTINGS, TABLE_RULES, TABLE_DOMAIN, COL_SETTINGS_SYSTEM, COL_SETTINGS_UNIQUE, COL_SETTINGS_DOMAIN_DEFAULT
from app.config.settings.SystemSettings import SystemSettings
from app.utils.db.Condition import EqualCondition, NotEqualCondition
from app.utils.exceptions import AggravatedException
from app.utils.logger.logger import logger, logger_api
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
    
    def update_system_settings(self, new_param: dict) -> tuple[bool, str]:

        self.sogo_db_manager.connect()

        #Get the current system settings, purposely put a "true" condition to check if there is only 1 row.
        cond_select = NotEqualCondition(param_name=COL_SETTINGS_UNIQUE.name, param_value=0)
        result  = list(self.sogo_db_manager.select_from_table(table_name=TABLE_SETTINGS.name,
                                               column_tuple=(COL_SETTINGS_SYSTEM.name,),
                                               condition=cond_select))
        size = len(result)
        if size > 1:
            #There is more than one row in table TABLE_SETTINGS which is not normal
            logger.error("Table %s has more than one row (%s}) which is not normal. Please check manually this table", TABLE_SETTINGS.name ,size)
            raise AggravatedException(f"Table {TABLE_SETTINGS.name} has more than one row ({size}) which is not normal. Please check manually this table")
        
        ret = -1
        if size == 0:
            #Empty, this is the first time SOGo is configured.
            logger.warning("Table %s is empty, which is normal if this is the first time you use SOGo", TABLE_SETTINGS.name)
            system_schema = SystemSettings()
            try:
                values = system_schema.load(new_param)
            except ValidationError as e:
                logger_api.error("Data received for system settings are not conformed %s", e)
                return False, str(e)
            ret = self.sogo_db_manager.insert_in_table(table_name=TABLE_SETTINGS.name,
                                               column_tuple=(COL_SETTINGS_UNIQUE.name, COL_SETTINGS_SYSTEM.name,COL_SETTINGS_DOMAIN_DEFAULT.name),
                                               values_tuple=[[1, values, {}]])
        if size == 1:
            #Merge the new data and check it
            current_settings: dict = result[0][0]
            current_settings.update(new_param)
            system_schema = SystemSettings()
            try:
                values = system_schema.load(current_settings)
            except ValidationError as e:
                logger_api.error("Data received for system settings are not conformed %s", e)
                return False, str(e)

            #Update the column
            cond_update = EqualCondition(param_name=COL_SETTINGS_UNIQUE.name, param_value=1)
            ret = self.sogo_db_manager.update_in_table(table_name=TABLE_SETTINGS.name,
                                               column_tuple=(COL_SETTINGS_SYSTEM.name,),
                                               values_list=[values],
                                               condition=cond_update)
        if ret != 1:
            #Only one row is supposed to be updated
            logger.error("Something went wrong when updating the system settings, rows updated: %s, should be 1", ret)
            return False, f"Something went wrong when updating the system settings, rows updated: {ret}, should be 1"

        return True, "OK"

