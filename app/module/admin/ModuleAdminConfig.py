from __future__ import annotations
from typing import TYPE_CHECKING, Any, Type, Callable

from marshmallow import EXCLUDE

from app.config.db import tables as tbl
from app.config.settings.SystemSettings import get_all_system_schemas
from app.config.settings.DomainSettings import get_all_domain_schemas
from app.config.settings.DynamicFormSettings import create_dynamic_dict_for_settings
from app.config.settings.SogoSchema import SogoSchema
from app.utils.dict import merge_patch, set_origin_from_settings
from app.utils.db.Condition import EqualCondition, NotEqualCondition, TrueCondition, Order
from app.utils.db.Table import Column
from app.utils.exceptions import AggravatedException, BugException, RequestException
from app.utils.logger.logger import logger, logger_api
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils import errors as err


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
        sogo_db_type = f"Client{process_settings.SOGO_P_DB_TYPE}"

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

    def _get_setting_from_table_settings(self, column_tuple: tuple) -> tuple[dict]:
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
        cond_select = NotEqualCondition(param_name=tbl.COL_SETTINGS_UNIQUE.name, param_value=0)
        result  = list(self.sogo_db_manager.select_from_table(table_name=tbl.TABLE_SETTINGS.name,
                                               column_tuple=column_tuple,
                                               condition=cond_select))
        size = len(result)
        if size > 1:
            #There is more than one row in table tbl.TABLE_SETTINGS which is not normal
            logger.error("Table %s has more than one row (%s}) which is not normal. Please check manually this table", tbl.TABLE_SETTINGS.name ,size)
            raise AggravatedException(f"Table {tbl.TABLE_SETTINGS.name} has more than one row ({size}) which is not normal. Please check manually this table")

        if size == 0:
            #Empty, this is the first time SOGo is configured.
            logger.warning("Table %s is empty, which is normal if this is the first time you use SOGo", tbl.TABLE_SETTINGS.name)
            ret: tuple = ({},)
            for _ in range(len(column_tuple)-1):
                ret += ret
            return ret

        ret = result[0]

        return ret


    def get_system_settings(self) -> dict:
        """
        Return the system settings or an empty dict if there is not

        :return: dict with current system settings
        :rtype: dict
        """

        return self._get_setting_from_table_settings((tbl.COL_SETTINGS_SYSTEM.name,))[0]

    def get_default_domain_settings(self) -> dict:
        """
        Return the default domain settings or an empty dict if there is not

        :return: dict with current default domain settings
        :rtype: dict
        """

        return self._get_setting_from_table_settings((tbl.COL_SETTINGS_DOMAIN_DEFAULT.name,))[0]

    def get_both_system_and_default_domain_settings(self) -> tuple:
        """
        Return a tuple of both system settings and default_domain_settings

        :return: _description_
        :rtype: tuple[dict]
        """

        return self._get_setting_from_table_settings((tbl.COL_SETTINGS_SYSTEM.name,tbl.COL_SETTINGS_DOMAIN_DEFAULT.name))

    def get_all_domains_settings(self, offset: int = 0, limit: int = 0,
                                 columns: tuple[Column, ...]|None = None,
                                 sort_by: Column|None = None,
                                 order: Order = Order.ASC) -> tuple[int,list]:
        """
        Return all the settings for scpecific domains.
        columns indicates which database column to query.

        sort_by is a column_anme to apply a sort mechanism

        order indicates the direction fo the sorting.

        :param columns: _description_
        :type columns: Column
        :param sort_by: _description_, defaults to ""
        :type sort_by: str, optional
        :param order: _description_, defaults to Order.ASC
        :type order: Order, optional
        """

        if columns is not None:
            for column in columns:
                if column not in tbl.TABLE_DOMAIN.columns:
                    raise BugException(f"Trying to query a column {column.name} that does not exist in {tbl.TABLE_DOMAIN.name}")
            column_tuple = tuple(col.name for col in columns)
        else:
            column_tuple = tuple(col.name for col in tbl.TABLE_DOMAIN.columns)

        if sort_by and sort_by not in tbl.TABLE_DOMAIN.columns:
            raise BugException(f"Trying to sort by a column {sort_by.name} that does not exist in {tbl.TABLE_DOMAIN.name}")

        self.sogo_db_manager.connect()

        #Get the current system settings, purposely put a "true" condition to check if there is only 1 row.
        cond_select = TrueCondition()
        count = self.sogo_db_manager.count_row_in_table(table_name=tbl.TABLE_DOMAIN.name, condition=cond_select)
        result = []
        for record in self.sogo_db_manager.select_from_table(table_name=tbl.TABLE_DOMAIN.name,
                                               column_tuple=column_tuple,
                                               condition=cond_select,
                                               offset=offset,
                                               limit=limit):
            record_dict = {}
            for idx, col in enumerate(column_tuple):
                if col == tbl.COL_DOMAIN_SETTINGS.name:
                    record_dict["settings"] = record[idx]
                else:
                    record_dict[col] = record[idx]
            result.append(record_dict)

        return count, result

    def get_one_domain_setting(self, domain_id:str, columns: tuple[Column, ...]|None = None) -> dict:
        """
        Get one domain setting for domain_id

        :param domain_id: _description_
        :type domain_id: str
        :return: _description_
        :rtype: dict
        """
        self.sogo_db_manager.connect()

        if columns is not None:
            for column in columns:
                if column not in tbl.TABLE_DOMAIN.columns:
                    raise BugException(f"Trying to query a column {column.name} that does not exist in {tbl.TABLE_DOMAIN.name}")
            column_tuple = tuple(col.name for col in columns)
        else:
            column_tuple = tuple(col.name for col in tbl.TABLE_DOMAIN.columns)

        #Get the current system settings, purposely put a "true" condition to check if there is only 1 row.
        cond_select = EqualCondition(param_name=tbl.COL_DOMAIN_NAME.name, param_value=domain_id)
        result = list(self.sogo_db_manager.select_from_table(table_name=tbl.TABLE_DOMAIN.name,
                                               column_tuple=column_tuple,
                                               condition=cond_select))
        size = len(result)
        if size > 1:
            #There is more than one row which is impossible as the domain_name is not duplicable
            logger.error("Table %s has more than one row (%s}) with the same domain_name: %s. Please check manually this table", tbl.TABLE_DOMAIN.name, size, domain_id)
            raise AggravatedException(f"Table {tbl.TABLE_SETTINGS.name} has more than one row ({size}) with the same domain_name {domain_id}. Please check manually this table")

        if size == 0:
            #Empty, the resource does not exist
            logger.warning("Table %s is empty, which is normal if this is the first time you use SOGo", tbl.TABLE_SETTINGS.name)
            raise RequestException("domain given does not exist", err.ERROR_DOMAIN_NAME_NOT_FOUND)

        ret: dict = {}
        for idx, col in enumerate(column_tuple):
            if col == tbl.COL_DOMAIN_SETTINGS.name:
                ret["settings"] = result[0][idx]
            else:
                ret[col] = result[0][idx]

        return ret


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
                updated_data_dict: dict = {}
                data_dict: dict[str, dict] = data.get(check_schema.subparent, [])
                for data_uid, data_values in data_dict.items():
                    updated_value = check_schema.load(data_values, unknown=EXCLUDE)
                    updated_data_dict[data_uid]=updated_value
                updated_data[check_schema.subparent] = updated_data_dict
            else:
                data_values = data.get(check_schema.subparent, {})
                updated_value = check_schema.load(data_values, unknown=EXCLUDE)
                updated_data[check_schema.subparent] = updated_value
        return updated_data


    def _update_setting_in_table_settings(self, new_param: dict, column_name: str, get_schema: Callable) -> tuple[int, dict]:
        """
        new_param is expected to be of JSON merge patch.
        If the subparent allows multiple entrees, it should be a dict key=uid, value=dict of param
        {
            subparent1: {
                            setting1.1: value1.1,
                            setting1.2: value1.2,
                        },
            subparent2: {
                            setting2.1: value2.1,
                            setting2.2: value2.2,
                        },
            subparent3: {
                    "uid1": {
                            setting3.0.1: value3.0.1,
                            setting3.0.2: value3.0.2,
                        },
                    "uid2": {
                            setting3.1.1: value3.1.1,
                            setting3.1.2: value3.1.2,
                        }
        }

        :param new_param: values for the settings
        :type new_param: dict
        :param new_param: column name of the settings (either system or domain_default)
        :type new_param: str
        :return: True if everything was ok, False with a string that explains the problem
        :rtype: tuple[bool, str]

        :raises: ValidationError()
        :raises: AggravatedException()
        """

        self.sogo_db_manager.connect()

        #Get the current system settings, purposely put a "true" condition to check if there is only 1 row.
        cond_select = NotEqualCondition(param_name=tbl.COL_SETTINGS_UNIQUE.name, param_value=0)
        result  = list(self.sogo_db_manager.select_from_table(table_name=tbl.TABLE_SETTINGS.name,
                                               column_tuple=(column_name,),
                                               condition=cond_select))
        size = len(result)
        if size > 1:
            #There is more than one row in table TABLE_SETTINGS which is not normal
            logger.error("Table %s has more than one row (%s}) which is not normal. Please check manually this table", tbl.TABLE_SETTINGS.name ,size)
            raise AggravatedException(f"Table {tbl.TABLE_SETTINGS.name} has more than one row ({size}) which is not normal", err.ERROR_TABLE_SYSTEM_NOT_UNIQUE)

        ret = -1
        values: dict = {}
        if size == 0:
            #Empty, this is the first time SOGo is configured.
            logger.warning("Table %s is empty, which is normal if this is the first time you use SOGo", tbl.TABLE_SETTINGS.name)
            clean_param: dict = {}
            merge_patch(new_param, clean_param)
            values = self._check_data(clean_param, get_schema)
            if column_name == tbl.COL_SETTINGS_SYSTEM.name:
                values_tuple = [1, values, {}]
            elif column_name == tbl.COL_SETTINGS_DOMAIN_DEFAULT.name:
                values_tuple = [1, {}, values]
            else:
                raise BugException(f"Trying to insert an unknown column in {tbl.TABLE_SETTINGS.name}: {column_name}", err.ERROR_BUG_UNKNWON_COLUMN)
            ret = self.sogo_db_manager.insert_in_table(table_name=tbl.TABLE_SETTINGS.name,
                                               column_tuple=(tbl.COL_SETTINGS_UNIQUE.name, tbl.COL_SETTINGS_SYSTEM.name,tbl.COL_SETTINGS_DOMAIN_DEFAULT.name),
                                               values_tuple=[values_tuple])
        if size == 1:
            #Merge the new data and check it
            current_settings: dict = result[0][0]
            merge_patch(new_param, current_settings)


            values = self._check_data(current_settings, get_schema)

            #Update the column
            cond_update = EqualCondition(param_name=tbl.COL_SETTINGS_UNIQUE.name, param_value=1)
            ret = self.sogo_db_manager.update_in_table(table_name=tbl.TABLE_SETTINGS.name,
                                               column_tuple=(column_name,),
                                               values_list=[values],
                                               condition=cond_update)
        if ret != 1:
            #Only one row is supposed to be updated
            logger.error("Something went wrong when updating the system settings, rows updated: %s, should be 1", ret)
            raise BugException(f"Something went wrong when updating the system settings, rows updated: {ret}, should be 1", err.ERROR_TABLE_SYSTEM_NOT_UNIQUE)

        return err.ERROR_NO_ERRROR, values


    def update_system_settings(self, new_param: dict) -> tuple[int, dict]:
        """
        Method to update/insert the system settings

        :param new_param: values for the settings
        :type new_param: dict
        :return: Return the code error and the new settings values
        :rtype: tuple[int, dict]
        """

        return self._update_setting_in_table_settings(new_param, tbl.COL_SETTINGS_SYSTEM.name, get_all_system_schemas)

    def update_domain_default_settings(self, new_param: dict) -> tuple[int, dict]:
        """
        Method to update/insert the default domain settings

        :param new_param: values for the settings
        :type new_param: dict
        :return: Return the code error and the new settings values
        :rtype: tuple[int, dict]
        """

        return self._update_setting_in_table_settings(new_param, tbl.COL_SETTINGS_DOMAIN_DEFAULT.name, get_all_domain_schemas)

    def create_domain_settings(self, new_param: dict) -> tuple[int, dict]:
        """
        Create new domain settings
        """

        self.sogo_db_manager.connect()
        domain_name = new_param["domain_name"]

        domain_cond = EqualCondition(tbl.COL_DOMAIN_NAME.name, domain_name)
        domain_result = list(self.sogo_db_manager.select_from_table(table_name=tbl.TABLE_DOMAIN.name,
                                               column_tuple=(tbl.COL_DOMAIN_NAME.name,),
                                               condition=domain_cond))
        if len(domain_result) > 0:
            raise RequestException(f"Domain's name '{domain_name}' already taken", err.ERROR_DOMAIN_NAME_TAKEN)

        domain_description = new_param["domain_description"]
        domain_info = new_param.get("domain_info", {})

        values_default = self.get_default_domain_settings()
        values_new = new_param.get("settings", {})

        origins = set_origin_from_settings(domain_name, values_new, values_default)

        values_default.update(values_new)
        values = self._check_data(values_default, get_all_domain_schemas)

        insert_values = [[domain_name, domain_description, domain_info, values, origins]]
        colums = (tbl.COL_DOMAIN_NAME.name, tbl.COL_DOMAIN_DESCRIPTION.name, tbl.COL_DOMAIN_INFO.name, tbl.COL_DOMAIN_SETTINGS.name, tbl.COL_DOMAIN_ORIGIN.name)

        #Insert in column
        row_updated = self.sogo_db_manager.insert_in_table(table_name=tbl.TABLE_DOMAIN.name,
                                            column_tuple=colums,
                                            values_tuple=insert_values)
        if row_updated != 1:
            #Only one row is supposed to be updated
            logger.error("Something went wrong when updating the system settings, rows updated: %s, should be 1", row_updated)
            raise BugException(f"Something went wrong when updating the system settings, rows updated: {row_updated}, should be 1", err.ERROR_TABLE_SYSTEM_NOT_UNIQUE)

        result = {
            "domain_name": domain_name,
            "domain_description": domain_description,
            "domain_info": domain_info,
            "settings": values,
            "origin": origins,
        } 

        return err.ERROR_NO_ERRROR, result

    def update_one_domain_settings(self, domain_id:str, new_param: dict) -> tuple[int, dict]:
        """
        Method to update the default domain settings

        :param new_param: values for the settings
        :type new_param: dict
        :return: Return the code error and the new settings values
        :rtype: tuple[int, dict]
        """

        self.sogo_db_manager.connect()

        # raise RequestException if domain not found
        stored_data = self.get_one_domain_setting(domain_id)

        merge_patch(new_param, stored_data)

        values = self._check_data(stored_data["settings"], get_all_domain_schemas)
        values_default = self.get_default_domain_settings()
        origins = set_origin_from_settings(domain_id, values, values_default)

        update_values = [stored_data["domain_description"], stored_data["domain_info"], values, origins]
        colums = (tbl.COL_DOMAIN_DESCRIPTION.name, tbl.COL_DOMAIN_INFO.name, tbl.COL_DOMAIN_SETTINGS.name, tbl.COL_DOMAIN_ORIGIN.name)

        #Update in column
        cond = EqualCondition(tbl.COL_DOMAIN_NAME.name, domain_id)
        row_updated = self.sogo_db_manager.update_in_table(table_name=tbl.TABLE_DOMAIN.name,
                                            column_tuple=colums,
                                            values_list=update_values,
                                            condition=cond)
        if row_updated != 1:
            #Only one row is supposed to be updated
            logger.error("Something went wrong when updating the system settings, rows updated: %s, should be 1", row_updated)
            raise BugException(f"Something went wrong when updating the system settings, rows updated: {row_updated}, should be 1", err.ERROR_TABLE_SYSTEM_NOT_UNIQUE)

        result = {
            "domain_name": domain_id,
            "domain_description": stored_data["domain_description"],
            "domain_info": stored_data["domain_info"],
            "settings": values,
            "origin": origins,
        }

        return err.ERROR_NO_ERRROR, result
    
    def delete_one_domain_setting(self, domain_id:str) -> int:
        """
        Delete onr 

        :param domain_id: _description_
        :raises RequestException: raise if 0 or more than 1 row would have been deleted
        :type domain_id: str
        """
        self.sogo_db_manager.connect()

        #Just use this method to check if the domain exist
        self.get_one_domain_setting(domain_id)

        cond = EqualCondition(tbl.COL_DOMAIN_NAME.name, domain_id)

        deleted_rows = self.sogo_db_manager.delete_row_in_table(tbl.TABLE_DOMAIN.name, cond, expected_row=1)

        return deleted_rows


