from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint


from app.interface.admin.InterfaceApiAdminConfig import InterfaceApiAdminConfig
from app.utils.logger.logger import logger_api

from .schema.adminConfig import AdminConfigSystemPostSchema, AdminConfigDomainPostSchema

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting



blp = Blueprint("ApiConfig", __name__, url_prefix="/adminConfig")

@blp.before_request
def init_admin_config() -> None:
    """
    Init the interface and others if needed
    """
    logger_api.debug("Calling before_request for ApiAdminConfig")
    process : ProcessSetting = g.process
    interface_api = InterfaceApiAdminConfig(process_setting=process)
    g.inter = interface_api

@blp.route("")
class ApiAdminConfig(MethodView):
    """
    Endpoint that return the dynamic settings structure
    """
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Return the dynamic settings structure
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_dynamic_setting_structure()

@blp.route("/all")
class ApiAdminConfigAll(MethodView):
    """
    Endpoint that return all the settings value
    """
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Return the system settings, the domain default settings, the list of rules and the list of domains
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_all_setting_value()

@blp.route("/system")
class ApiAdminConfigSystem(MethodView):
    """
    Endpoint that return the list of the system settings
    """
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Return the system settings
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_all_setting_system()

    @blp.arguments(AdminConfigSystemPostSchema, example=AdminConfigSystemPostSchema.example())
    @blp.response(200)
    def post(self, new_data: dict) -> ResponseReturnValue:
        """
        Endpoint to post new system settings

        :param new_data: See :py:class:`~app.api.admin.schema.AdminConfigSystemPostSchema`
        :type new_data: dict
        """
        print(new_data)
        interface_api : InterfaceApiAdminConfig = g.inter
        ret = interface_api.update_all_setting_system(new_data["settings"])
        return ret


@blp.route("/domain")
class ApiAdminConfigDomain(MethodView):
    """
    Endpoint that return the list of domains that have been specified
    """
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Return the list of domains name that have been defined
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_list_of_domain()


@blp.route("/domain/<string:domain_name>")
class ApiAdminConfigDomainSettings(MethodView):
    """
    Endpoint that return the list of settings for a domain (or the default)
    """
    @blp.response(200)
    def get(self, domain_name: str) -> ResponseReturnValue:
        """
        Return the specified domain settings, or the default one.
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        if domain_name == "default":
            return interface_api.get_all_setting_domain_default()
        ret = interface_api.get_all_setting_domain(domain_name)
        if ret:
            return ret
        return {"error": f"domain_name {domain_name} not found"}, 400

    @blp.arguments(AdminConfigDomainPostSchema, example=AdminConfigDomainPostSchema.example())
    @blp.response(200)
    def post(self, new_data: dict, domain_name: str) -> ResponseReturnValue:
        """
        Endpoint to post new system settings

        :param new_data: See :py:class:`~app.api.admin.schema.AdminConfigSystemPostSchema`
        :type new_data: dict
        """
        # logger_api.debug("new_data: %s", new_data)
        # logger_api.debug("domain_name: %s", domain_name)
        interface_api : InterfaceApiAdminConfig = g.inter
        if domain_name == "default":
            ret = interface_api.update_all_setting_domain_default(new_data["settings"])
        else:
            raise NotImplementedError("Not implemented update specficed domain")
        return ret

@blp.route("/rules")
class ApiAdminConfigRule(MethodView):
    """
    Endpoint that return a list of all rules
    """
    @blp.response(200)
    def get(self) -> ResponseReturnValue:
        """
        Return the list of rules defined
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        return interface_api.get_list_of_rule()

@blp.route("/rules/<int:rule_id>")
class ApiAdminConfigRuleSetting(MethodView):
    """
    Endpoint that return all the settings of the rule_id
    """
    @blp.response(200)
    def get(self, rule_id: int) -> ResponseReturnValue:
        """
        Return the rules settings
        """
        interface_api : InterfaceApiAdminConfig = g.inter
        ret =  interface_api.get_all_setting_rule(rule_id)
        if ret:
            return ret
        return {"error": f"rule_id {rule_id} not found"}, 400
