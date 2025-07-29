


class ModuleConfig:
    """
    Interface between ConfigSystemDOmain and modules
    """
    def __init__(self):
        is_configured = False

    def check_for_system_domain_config(self) -> bool:
        """
        Check if there is valid system and domain settings in database
        """
        a = 2
