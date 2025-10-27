from __future__ import annotations
from typing import TYPE_CHECKING, Any, Type, Callable

from marshmallow.exceptions import ValidationError
from marshmallow import EXCLUDE

from app.config.db.tables import TABLE_SETTINGS, TABLE_RULES, TABLE_DOMAIN, COL_SETTINGS_SYSTEM, COL_SETTINGS_UNIQUE, COL_SETTINGS_DOMAIN_DEFAULT
from app.config.settings.SystemSettings import get_all_system_schemas
from app.config.settings.DomainSettings import get_all_domain_schemas
from app.config.settings.DynamicFormSettings import create_dynamic_dict_for_settings
from app.config.settings.SogoSchema import SogoSchema
from app.utils.db.Condition import EqualCondition, NotEqualCondition
from app.utils.exceptions import AggravatedException, BugException
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
    
    def get_dynamic_form_settings(self) -> dict:
        """
        Return the full dictionnary with the dynamic form format

        :return: The full dynamic form
        :rtype: dict
        """
        full_form: dict = {}
        #System settings
        full_form["system"] = []
        for schema in get_all_system_schemas():
            full_form["system"].append(create_dynamic_dict_for_settings(schema()))

        #Domain settings
        full_form["domain"] = []
        for schema in get_all_domain_schemas():
            full_form["domain"].append(create_dynamic_dict_for_settings(schema()))


        return full_form

    def _get_setting_from_table_settings(self, column_name: str) -> dict:
        """
        Generic function that fetch, test and return the configuration/dict
        found in the `column_table` of table `TABLE_SETTINGS`

        This table should only be one row

        :param column_name: name of the colum from `TABLE_SETTINGS` to fetch the data
        :type column_name: str
        :raises AggravatedException: if `TABLE_SETTINGS` has more than one row
        :return: the data found in the column. Can be empty if this is the first time setting up SOGo
        :rtype: dict
        """
        self.sogo_db_manager.connect()

        #Get the current system settings, purposely put a "true" condition to check if there is only 1 row.
        cond_select = NotEqualCondition(param_name=COL_SETTINGS_UNIQUE.name, param_value=0)
        result  = list(self.sogo_db_manager.select_from_table(table_name=TABLE_SETTINGS.name,
                                               column_tuple=(column_name,),
                                               condition=cond_select))
        size = len(result)
        if size > 1:
            #There is more than one row in table TABLE_SETTINGS which is not normal
            logger.error("Table %s has more than one row (%s}) which is not normal. Please check manually this table", TABLE_SETTINGS.name ,size)
            raise AggravatedException(f"Table {TABLE_SETTINGS.name} has more than one row ({size}) which is not normal. Please check manually this table")

        ret = {}
        if size == 0:
            #Empty, this is the first time SOGo is configured.
            logger.warning("Table %s is empty, which is normal if this is the first time you use SOGo", TABLE_SETTINGS.name)

        if size == 1:
            #Merge the new data and check it
            ret = result[0][0]

        return ret


    def get_system_settings(self) -> dict:
        """
        Return the system settings or an empty dict if there is not

        :return: dict with current system settings
        :rtype: dict
        """

        return self._get_setting_from_table_settings(COL_SETTINGS_SYSTEM.name)

    def get_default_domain_settings(self) -> dict:
        """
        Return the default domain settings or an empty dict if there is not

        :return: dict with current default domain settings
        :rtype: dict
        """

        return self._get_setting_from_table_settings(COL_SETTINGS_DOMAIN_DEFAULT.name)


    def _check_data(self, data: dict, get_all_schemas: Callable[[], list[Type[SogoSchema]]]) -> dict:
        """
        The data here is either the request data merged with the database data
        OR, if this is the first time setting up SOGo, just the request data.
        In both cases, data should satisfied all the domains schema.

        After being validated by the schema.load() method, the function return
        the dict completed by the default value.

        :raises: ValidationError()
        """
        updated_data = {}
        for schema in get_all_schemas():
            check_schema = schema()
            if check_schema.is_duplicable:
                updated_data_list = []
                data_list: list[dict] = data.get(check_schema.subparent, [])
                for data_values in data_list:
                    updated_value = check_schema.load(data_values, unknown=EXCLUDE)
                    updated_data_list.append(updated_value)
                updated_data[check_schema.subparent] = updated_data_list
            else:
                data_values = data.get(check_schema.subparent, {})
                updated_value = check_schema.load(data_values, unknown=EXCLUDE)
                updated_data[check_schema.subparent] = updated_value
        return updated_data

    def _update_current_setting(self, current_settings: dict[str, Any], new_settings: dict[str, dict], get_all_schemas: Callable[[], list[Type[SogoSchema]]]) -> None:
        """
        Update the current settings from database with the new ones before validation.
        We can't directly do current_settings.update(new_settings) because the dict is nested and schema
        that are duplicable (like USER_SOURCE) are list.
        We directly updates current_settings instead of creatinf and returning a new one.

        :param current_settings: current settings in the database
        :type current_settings: dict
        :param new_settings: new settings send with the api post request
        :type new_settings: dict
        :param get_all_schemas: methods the return the list of schemas
        :type get_all_schemas: Callable[[], list[Type[SogoSchema]]]
        """

        def _easy_find_for_duplicable(list_block: list[dict], uid_param: str) -> dict[str, int]:
            """
            Return a dict with the uid as key and index in the list as value

            :param list_block: list of param from duplicable schema
            :type list_block: list[dict]
            :param uid_param: unique id for the schema
            :type uid_param: str
            :return: Result
            :rtype: dict[str, int]
            """
            ret: dict[str, int] = {}
            for idx, block in enumerate(list_block):
                uid = block[uid_param]
                ret[uid] = idx
            return ret

        for schema in get_all_schemas():
            subparent = schema.subparent
            schema_uid = schema.is_uid
            if subparent in current_settings:
                # subparent is in current_settings, check if this a duplicable subparent or not
                if schema.is_duplicable:
                    # Duplicable, the subparent is a list of one or several settings blocks
                    if subparent in new_settings:
                        #Hack to only do one for each loop for current settings
                        cur_blocks_ordered = _easy_find_for_duplicable(current_settings[subparent], schema_uid)
                        block: dict
                        for block in new_settings[subparent]:
                            # The api request should always precise the old_uid value, to make sure to update the correct one
                            # If there is no old_uid, we considred this is not an update
                            old_uid = block.get(f"OLD_{schema_uid}", block[schema_uid])
                            # Check if this uid exist in current_settings
                            current_block_index: int = cur_blocks_ordered.get(old_uid, -1)
                            if current_block_index != -1:
                                #It exists, update the block
                                current_block: dict = current_settings[subparent][current_block_index]
                                current_block.update(block)
                                current_block.pop(f"OLD_{schema_uid}", None)
                            else:
                                #It does not exists (new block), add it to the list
                                block.pop(f"OLD_{schema_uid}", None)
                                current_settings[subparent].append(block)
                else:
                    # Not duplicable, subparent value is directly a dict
                    current_settings[subparent].update(new_settings.get(subparent, {}))
            else:
                # Subparent is not in current_settings, that can happend if there is new subparent after an update
                current_settings[subparent] = new_settings.get(subparent, {})
            


    def _update_setting_in_table_settings(self, new_param: dict, column_name: str, get_schema: Callable) -> tuple[bool, str]:
        """
        new_param should direclty be a nested dictionnary for each subparent param:value
        If the subparent allows multiple entrees, it should be an array of dict param:value
        {
            subparent1: {
                            setting1.1: value1.1,
                            setting1.2: value1.2,
                        },
            subparent2: {
                            setting2.1: value2.1,
                            setting2.2: value2.2,
                        },
            subparent3: [{
                            setting3.0.1: value3.0.1,
                            setting3.0.2: value3.0.2,
                        },
                        {
                            setting3.1.1: value3.1.1,
                            setting3.1.2: value3.1.2,
                        }]
        }

        :param new_param: values for the settings
        :type new_param: dict
        :param new_param: column name of the settings (either system or domain_default)
        :type new_param: str
        :return: True if everything was ok, False with a string that explains the problem
        :rtype: tuple[bool, str]
        """
                
        self.sogo_db_manager.connect()

        #Get the current system settings, purposely put a "true" condition to check if there is only 1 row.
        cond_select = NotEqualCondition(param_name=COL_SETTINGS_UNIQUE.name, param_value=0)
        result  = list(self.sogo_db_manager.select_from_table(table_name=TABLE_SETTINGS.name,
                                               column_tuple=(column_name,),
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
            try:
                values = self._check_data(new_param, get_schema)
            except ValidationError as e:
                logger_api.error("Data received for %s settings are not conformed %s", column_name, e)
                return False, str(e)
            if column_name == COL_SETTINGS_SYSTEM.name:
                values_tuple = [1, values, {}]
            elif column_name == COL_SETTINGS_DOMAIN_DEFAULT.name:
                values_tuple = [1, {}, values]
            else:
                raise BugException(f"Trying to insert an unknown column in {TABLE_SETTINGS.name}: {column_name}")
            ret = self.sogo_db_manager.insert_in_table(table_name=TABLE_SETTINGS.name,
                                               column_tuple=(COL_SETTINGS_UNIQUE.name, COL_SETTINGS_SYSTEM.name,COL_SETTINGS_DOMAIN_DEFAULT.name),
                                               values_tuple=[values_tuple])
        if size == 1:
            #Merge the new data and check it
            current_settings: dict = result[0][0]
            self._update_current_setting(current_settings, new_param, get_schema)
            try:
                values = self._check_data(current_settings, get_schema)
            except ValidationError as e:
                logger_api.error("Data received for %s settings are not conformed %s", column_name, e)
                return False, str(e)

            #Update the column
            cond_update = EqualCondition(param_name=COL_SETTINGS_UNIQUE.name, param_value=1)
            ret = self.sogo_db_manager.update_in_table(table_name=TABLE_SETTINGS.name,
                                               column_tuple=(column_name,),
                                               values_list=[values],
                                               condition=cond_update)
        if ret != 1:
            #Only one row is supposed to be updated
            logger.error("Something went wrong when updating the system settings, rows updated: %s, should be 1", ret)
            return False, f"Something went wrong when updating the system settings, rows updated: {ret}, should be 1"

        return True, "OK"


    def update_system_settings(self, new_param: dict) -> tuple[bool, str]:
        """
        Method to update/insert the default domain settings

        :param new_param: values for the settings
        :type new_param: dict
        :return: True if everything was ok, False with a string that explains the problem
        :rtype: tuple[bool, str]
        """

        return self._update_setting_in_table_settings(new_param, COL_SETTINGS_SYSTEM.name, get_all_system_schemas)

    def update_domain_default_settings(self, new_param: dict) -> tuple[bool, str]:
        """
        Method to update/insert the default domain settings

        :param new_param: values for the settings
        :type new_param: dict
        :return: True if everything was ok, False with a string that explains the problem
        :rtype: tuple[bool, str]
        """

        return self._update_setting_in_table_settings(new_param, COL_SETTINGS_DOMAIN_DEFAULT.name, get_all_domain_schemas)
