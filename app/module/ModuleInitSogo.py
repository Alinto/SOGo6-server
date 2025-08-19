from __future__ import annotations
from typing import TYPE_CHECKING

from importlib import import_module

from app.utils.logger.logger import logger
from app.utils.exceptions import AggravatedException
from app.utils.module.importManager import import_and_instantiate_manager
from app.config.db.tables import ALL_TABLES

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL



class ModuleInitSogo:
    """
    This module class has all the methods to check and init sogo when the application is starting
    """

    def __init__(self, process_settings: ProcessSetting):
        """"
        process_settings: Object with all the process settings, necessary to start sogo
        init_ok: boolean, True means sogo is correctly initialized
        first_init: boolean, True means it's the first time sogo is launched (initiailiation ok but database empty)
        errors: if init_ok is False, list of strings with the errors
        """
        self.process_settings  = process_settings
        self.init_ok: bool     = False
        self.first_init: bool  = True
        self.errors: list[str] = []

    def check_redis(self) -> None:
        """
        Check sogo can reach the reddis cache
        """
        pass

    def check_sogo_database(self) -> None:
        """
        Check the database, meamning connection and structure
        """
        # For now, SOGo 6 forces the use of a postgresql database for its own data
        # If we want to change in the future, we must import the manager dynamically
        # to avoid a complete code rewritting.
        fake_process_settings_db = "PostgreSQL"
        sogo_db_type = f"Client{fake_process_settings_db}"

        sogo_db_manager: ClientSQL = import_and_instantiate_manager(module_path="app.manager.db",
                                                         module_and_class_name=sogo_db_type,
                                                         module_args=self.process_settings.get_db_settings())

        # Check tables
        table_ok = []
        for table in ALL_TABLES:
            temp_error = []
            db_table_info = sogo_db_manager.get_table_info(table.name)
            if db_table_info:
                #Check the Columns
                for column in table.columns:
                    if not column.name in db_table_info:
                        self.errors.append(f"Table {table.name}'s colum {column.name} was not found in database")
                        continue
                    if db_table_info[column.name] not in column.data_type_check:
                        self.errors.append(f"Table {table.name}'s colum {column.name} was found but from data_type different (expected among {column.data_type_check} and found {db_table_info[column.name]})")
                table_ok.append(table.name)
            else:
                #Table missing, it may be normal if this is the first init
                temp_error.append(f"Table {table.name} missing")

        if not table_ok:
            #No tables already set, SOGo has not been set yet
            logger.warning("SOGo database is emtpy. It's normal if this is the first time you run it")
            sogo_db_manager.create_several_table(ALL_TABLES)
        elif temp_error:
            # Some tables are ok, the others not. SOGo is in an unknwon state
            self.errors.extend(temp_error)
        elif len(table_ok) == len(ALL_TABLES):
            #All tables are ok
            self.first_init = False
        sogo_db_manager.close()
    
    def check_agent(self) -> None:
        """
        Check agent celery
        """
        pass

