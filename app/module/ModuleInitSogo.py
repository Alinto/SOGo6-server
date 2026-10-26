from __future__ import annotations
from typing import TYPE_CHECKING

from os import getpid

from app.config.db.tables import ALL_TABLES
from app.manager.cache.ClientRedis import ClientRedis
from app.module.common_module import get_sogo6_database
from app.utils.logger.logger import logger


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

    def get_cache(self) -> ClientRedis:
        """
        Instantiate and return the cache client

        :return: _description_
        :rtype: ClientRedis
        """
        #TODO mache an abstract cache_client instead of directly use redis_client.
        redis_conf = self.process_settings.get_redis_settings()
        cache_client = ClientRedis(**redis_conf)

        return cache_client

    def check_cache(self) -> None:
        """
        Check sogo can reach the reddis cache.
        """
        cache_client = self.get_cache()

        # Test connectivity
        cache_client.ping()

        key = f"init:{getpid()}"
        # Test writting, reading and deleting
        cache_client.set(key, "simplestring", 60)
        if ret:= cache_client.get(key, str) != "simplestring":
            self.errors.append(f"Cache client did not read the correct string {ret}")
        cache_client.delete(key)
        cache_client.close()




    def check_sogo_database(self) -> None:
        """
        Check the database, meamning connection and structure
        """
        sogo_db_manager: ClientSQL = get_sogo6_database(self.process_settings)

        # Check tables
        table_ok = []
        temp_error = []
        for table in ALL_TABLES:
            db_table_info = sogo_db_manager.get_table_info(table.name)
            if db_table_info:
                #Check the Columns
                for column in table.columns:
                    if not column.name in db_table_info:
                        self.errors.append(f"Table {table.name}'s column {column.name} was not found in database")
                        continue
                    if db_table_info[column.name] not in column.data_type_check:
                        self.errors.append(f"Table {table.name}'s column {column.name} was found but from data_type different (expected among {column.data_type_check} and found {db_table_info[column.name]})")
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
            #TODO add the update from version here
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

