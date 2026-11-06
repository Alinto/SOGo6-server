from __future__ import annotations
from typing import TYPE_CHECKING

from os import getpid

from packaging.version import InvalidVersion, Version

from app import __version__
from app.config.db.tables import ALL_TABLES, TABLE_SETTINGS
from app.manager.cache.ClientRedis import ClientRedis
from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.module.common_module import get_sogo6_database
from app.update import get_versions_to_update, run_update
from app.utils.exceptions import AggravatedException
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

        If the structure is wrong, try to update the database from the stored version
        """
        sogo_db_manager: ClientSQL = get_sogo6_database(self.process_settings)
        table_ok, schema_errors = self._check_tables(sogo_db_manager)

        if not table_ok:
            #No tables already set, SOGo has not been set yet
            logger.warning("SOGo database is emtpy. It's normal if this is the first time you run it")
            sogo_db_manager.create_several_table(ALL_TABLES)
            sogo_db_manager.close()
            return

        # Must be closed before the updates: on MariaDB, its read transaction would block their ALTER
        sogo_db_manager.close()

        if schema_errors:
            self._update_database(schema_errors)
        else:
            self._store_version_if_newer()
        if not self.errors:
            self.first_init = False

    def _check_tables(self, sogo_db_manager: ClientSQL) -> tuple[list[str], list[str]]:
        """
        Compare the tables and columns of the database with the expected ones. The order of the columns
        does not matter: a column added by an update is at the end of the table.

        :return: The name of the tables found and the differences with the expected structure
        :rtype: tuple[list[str], list[str]]
        """
        table_ok = []
        schema_errors = []
        for table in ALL_TABLES:
            db_table_info = sogo_db_manager.get_table_info(table.name)
            if db_table_info:
                #Check the Columns
                for column in table.columns:
                    if not column.name in db_table_info:
                        schema_errors.append(f"Table {table.name}'s column {column.name} was not found in database")
                        continue
                    if db_table_info[column.name] not in column.data_type_check:
                        schema_errors.append(f"Table {table.name}'s column {column.name} was found but from data_type different (expected among {column.data_type_check} and found {db_table_info[column.name]})")
                table_ok.append(table.name)
            else:
                #Table missing, it may be normal if this is the first init
                schema_errors.append(f"Table {table.name} missing")
        return table_ok, schema_errors

    def _update_database(self, schema_errors: list[str]) -> None:
        """
        Apply the updates between the stored version and the current one, then check the database again.
        The differences are real errors if there is no update to apply.

        :param schema_errors: Differences found with the expected structure
        :type schema_errors: list[str]
        :raises AggravatedException: if there is no stored version or if an update failed
        """
        stored_version = self._get_stored_version()
        if stored_version is None:
            raise AggravatedException(f"The structure of the database is wrong and no version is stored in table {TABLE_SETTINGS.name}: {schema_errors}")

        current_version = Version(__version__)
        if current_version < stored_version:
            #TODO rollback the database to the current version
            logger.error("SOGo %s is older than its database %s, rollback is not supported", current_version, stored_version)
            self.errors.extend(schema_errors)
            return

        versions_to_update = get_versions_to_update(stored_version, current_version)
        if not versions_to_update:
            self.errors.extend(schema_errors)
            return

        for version in versions_to_update:
            logger.info("Updating the database to version %s", version)
            run_update(version)
            # Stored after each update so a restart continues from the one that failed
            self._set_stored_version(str(version))

        sogo_db_manager: ClientSQL = get_sogo6_database(self.process_settings)
        _, remaining_errors = self._check_tables(sogo_db_manager)
        sogo_db_manager.close()
        if remaining_errors:
            self.errors.extend(remaining_errors)
            return

        self._set_stored_version(__version__)

    def _store_version_if_newer(self) -> None:
        """
        Store the current version when no update was needed. SOGo may not be configured yet, in
        this case there is no row to update and the version will be stored with the first settings.
        """
        stored_version = self._get_stored_version()
        if stored_version is not None and Version(__version__) > stored_version:
            self._set_stored_version(__version__)

    def _get_stored_version(self) -> Version | None:
        """
        Return the version stored in the database, None if there is not

        :raises AggravatedException: if the stored version is invalid
        """
        config_module = ModuleAdminConfig(self.process_settings)
        stored_version = config_module.get_version()
        config_module.close()
        if not stored_version:
            return None
        try:
            return Version(stored_version)
        except InvalidVersion as e:
            raise AggravatedException(f"The version stored in table {TABLE_SETTINGS.name} is invalid: {stored_version}") from e

    def _set_stored_version(self, version: str) -> None:
        """
        Store a version in the database
        """
        config_module = ModuleAdminConfig(self.process_settings)
        config_module.set_version(version)
        config_module.close()

    
    def check_agent(self) -> None:
        """
        Check agent celery
        """
        pass

