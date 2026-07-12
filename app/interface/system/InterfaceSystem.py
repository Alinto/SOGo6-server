from app.config.settings.SystemSettings import SystemSettingsObj, SystemSettings
from app.utils.api.ApiBaseResponse import create_api_base_response

class InterfaceSystem:
    """
    Interface for api System
    """
    def __init__(self, system_settings: dict):
        self.system = SystemSettingsObj(system_settings[SystemSettings.subparent])

    def get_ui_system_param(self) -> tuple[dict, int]:
        """
        Return the two system parameters needed by the UI

        :return: _description_
        :rtype: tuple[dict, int]
        """
        ret = {
            "SOGO_S_DIRECT_LOGIN": self.system.SOGO_S_DIRECT_LOGIN
        }

        return create_api_base_response({"system": ret})
