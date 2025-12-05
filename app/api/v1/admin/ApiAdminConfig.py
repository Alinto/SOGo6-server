from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g, Response
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.interface.admin.InterfaceApiAdminConfig import InterfaceApiAdminConfig
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.logger.logger import logger_api

from .schema import adminConfig as sch

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.utils.api.pagin_sort_filter import FakePaginationParameters



blp = Blueprint("ApiConfig", __name__, url_prefix="/config")

# def my_pagination_metadata(page, page_size, item_count):
#     return {"data": "hey i'm custom"}

# blp._make_pagination_metadata = my_pagination_metadata

@blp.before_request
def init_admin_config() -> None:
    """
    Init the interface and others if needed
    """
    logger_api.debug("Calling before_request for ApiAdminConfig")
    process : ProcessSetting = g.process
    interface_api = InterfaceApiAdminConfig(process_setting=process)
    g.inter = interface_api

@blp.route("/dynamic-form")
class ApiAdminConfig(MethodView):
    """
    Action

    Endpoint that return the dynamic settings structure
    """
    @blp.response(200, sch.AdminConfigDynamicFormSchemaRet)
    def get(self) -> ResponseReturnValue:
        """
        Action, return the dynamic settings structure
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_dynamic_setting_structure()


@blp.route("/system")
class ApiAdminConfigSystem(MethodView):
    """
    Singleton, can't be created, only modified

    Endpoint that return the list of the system settings
    """
    @blp.response(200, sch.AdminConfigSystemGetRetSchema, example=sch.AdminConfigSystemGetRetSchema.example())
    def get(self,) -> ResponseReturnValue:
        """
        Singleton, fetch the system settings
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_all_setting_system()

    @blp.arguments(sch.AdminConfigSystemPatchSchema, example=sch.AdminConfigSystemPatchSchema.example(), error_status_code=400)
    @blp.response(200, sch.AdminConfigSystemGetRetSchema, example=sch.AdminConfigSystemGetRetSchema.example())
    def patch(self, new_data: dict) -> ResponseReturnValue:
        """
        Singleton, update the system settings
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.update_all_setting_system(new_data["settings"])

@blp.route("/domain-default")
class ApiAdminConfigDefaultDomain(MethodView):
    """
    Singleton, can't be created, only modified

    Endpoint for the default domain setting
    """
    @blp.response(200, sch.AdminConfigDefaultDomainGetSchema, example=sch.AdminConfigDefaultDomainGetSchema.example())
    def get(self,) -> ResponseReturnValue:
        """
        Singleton, fetch the default domain setting
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_all_setting_domain_default()

    @blp.arguments(sch.AdminConfigDefaultDomainPatchSchema, example=sch.AdminConfigDefaultDomainPatchSchema.example(), error_status_code=400)
    @blp.response(200, sch.AdminConfigDefaultDomainGetSchema, example=sch.AdminConfigDefaultDomainGetSchema.example())
    def patch(self, new_data: dict) -> ResponseReturnValue:
        """
        Singleton, update the default domain setting
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.update_all_setting_domain_default(new_data["settings"])

@blp.route("/domains")
class ApiAdminConfigDomain(MethodView):
    """
    Collection, each resource is the sogo's settings associated to a domain
    """
    @blp.paginate(page=1, page_size=20, max_page_size=100)
    @blp.response(200)
    def get(self, pagination_parameters: FakePaginationParameters) -> ResponseReturnValue:
        """
        Get the list of domains settings
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        first = pagination_parameters.first_item
        last = pagination_parameters.last_item
        pagination_parameters.item_count, ret, status  = interface_api.get_all_domain_settings(first, last)
        return ret, status

    @blp.arguments(sch.AdminConfigDomainPostSchema, example=sch.AdminConfigDomainPostSchema.example(), error_status_code=400)
    @blp.response(200, sch.AdminConfigDomainGetSchema, example=sch.AdminConfigDomainGetSchema.example())
    @blp.response(400, sch.ApiBaseResponse)
    def post(self, new_data: dict) -> ResponseReturnValue:
        """
        Create a new set of settings for a domain
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        ret = interface_api.post_new_domain_settings(new_data)
        return ret


@blp.route("/domains/<string:domain_name>")
class ApiAdminConfigDomainSettings(MethodView):
    """
    Endpoint that return the list of settings for a domain (or the default)
    """
    @blp.response(200)
    def get(self, domain_name: str) -> ResponseReturnValue:
        """
        Resource, get the specified domain settings
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        ret = interface_api.get_domain_settings(domain_name)
        return ret

    @blp.arguments(sch.AdminConfigDomainPatchSchema, example=sch.AdminConfigDomainPatchSchema.example(), error_status_code=400)
    @blp.response(200)
    def patch(self, new_data: dict, domain_name: str) -> ResponseReturnValue:
        """
        Resource, update the specified domain settings
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.update_domain_settings(domain_name, new_data)
    
    @blp.response(200)
    def delete(self, domain_name: str) -> None|ResponseReturnValue:
        """
        Resource, delete specified domain settings
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        ret, code = interface_api.delete_domain_settings(domain_name)
        if code == 200:
            return None
        return ret, code
        
# @blp.route("/rulesList")
# class ApiAdminConfigRule(MethodView):
#     """
#     Endpoint that return a list of all rules
#     """
#     @blp.response(200)
#     def get(self) -> ResponseReturnValue:
#         """
#         Return the list of rules defined
#         """
#         interface_api : InterfaceApiAdminConfig = g.inter
#         return interface_api.get_list_of_rule()

#     @blp.arguments(sch.AdminConfigSystemPatchSchema, example=sch.AdminConfigSystemPatchSchema.example())
#     @blp.response(200)
#     def delete(self, data: dict) -> None:
#         """
#         _summary_

#         :param data: _description_
#         :type data: _type_
#         """
#         print(f"delete: {data}")

# @blp.route("/rules/<int:rule_id>")
# class ApiAdminConfigRuleSetting(MethodView):
#     """
#     Endpoint that return all the settings of the rule_id
#     """
#     @blp.response(200)
#     def get(self, rule_id: int) -> ResponseReturnValue:
#         """
#         Return the rules settings
#         """
#         interface_api : InterfaceApiAdminConfig = g.inter
#         ret =  interface_api.get_all_setting_rule(rule_id)
#         if ret:
#             return ret
#         return {"error": f"rule_id {rule_id} not found"}, 400

# @blp.route("/all")
# class ApiAdminConfigAll(MethodView):
#     """
#     Action, GET

#     Endpoint that return all the settings value
#     """
#     @blp.response(200)
#     def get(self) -> ResponseReturnValue:
#         """
#         Return the system settings, the domain default settings, the list of rules and the list of domains
#         """
#         interface_api : InterfaceApiAdminConfig = g.inter
#         ret = interface_api.get_all_setting_value()
#         return create_api_base_response(ret)