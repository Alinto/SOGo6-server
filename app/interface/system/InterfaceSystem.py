from app.config.settings.SystemSettings import SystemSettingsObj, SystemSettings
from app.config.settings.DomainSettings import AuthSettingsObj, AuthSettings
from app.utils.api.ApiBaseResponse import create_api_base_response

class InterfaceSystem:
    """
    Interface for api System
    """
    def __init__(self, system_settings: dict, default_domain: dict):
        self.system = SystemSettingsObj(system_settings[SystemSettings.subparent])
        self.auth_default = AuthSettingsObj(default_domain[AuthSettings.subparent])

    def get_ui_system_param(self) -> tuple[dict, int]:
        """
        Return the two system parameters needed by the UI

        :return: _description_
        :rtype: tuple[dict, int]
        """
        ret = {
            "SOGO_S_DIRECT_LOGIN": self.system.SOGO_S_DIRECT_LOGIN
        }
        if self.system.SOGO_S_DIRECT_LOGIN:
            #We must fetch the default domain for rember password here
            ret["SOGO_D_PWD_RECOVERY"] = self.auth_default.SOGO_D_PWD_RECOVERY

        return create_api_base_response({"system": ret}), 200
