from __future__ import annotations
from typing import TYPE_CHECKING

from importlib import import_module

from app.utils.logger.logger import logger
from app.utils.exceptions import AggravatedException
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

    def check_redis(self):
        """
        Check sogo can reach the reddis cache
        """
        pass

    def check_sogo_database(self):
        """
        Check the database, meamning connection and structure
        """
        # For now, SOGo 6 foeces the use of a postgresql databse for its own data
        # If we want of change in the future, we must import the manager dynamically
        # with a value from process_settings
        fake_process_settings_db = "PostgreSQL"
        sogo_db_type = f"Client{fake_process_settings_db}"

        # import the manager
        try:
            sogo_db_manager_module     = import_module(f"app.manager.db.{sogo_db_type}")
            sogo_db_manager_class      = getattr(sogo_db_manager_module, sogo_db_type)
            sogo_db_manager: ClientSQL = sogo_db_manager_class(**self.process_settings.get_db_settings())
        except (ModuleNotFoundError, NameError, TypeError) as e:
            logger.error("Cannot instantiate sogo database manager, config or package problem: %s", e)
            raise AggravatedException("Cannot instantiate sogo database") from e
        except Exception as e:
            logger.error("Cannot instantiate sogo database manager, unexpecte error: %s", e)
            raise AggravatedException("Cannot instantiate sogo database") from e

        # Check tables
        table_ok = []
        for table in ALL_TABLES:
            db_table_info = sogo_db_manager.get_table_info(table.name)
            if db_table_info:
                #Check the Columns
                for column in table.columns:
                    if not column.name in db_table_info:
                        self.errors.append(f"Table {table.name}'s colum {column.name} was not found in database")
                        continue
                    if db_table_info[column.name] != column.data_type:
                        self.errors.append(f"Table {table.name}'s colum {column.name} was found but from data_type different (expected {column.data_type} and found {db_table_info[column.name]})")

        self.init_ok = True

        # If no error, create the tables




    
    def check_agent(self):
        """
        Check agent celery
        """
        pass

