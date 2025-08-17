from app.config.settings.FrontWrapperSettings import example


class InterfaceApiAdminConfig:
    """
    Interface for the api ApiAdminConfig
    """
    def __init__(self):
        pass

    def get_dynamic_setting_structure(self) -> None:
        """
        Return the dynamic table
        """
        return example

    def get_all_setting_value(self) -> None:
        """
        Return all the settings
        """
        all_settings = {"system": self.get_all_setting_system(),
                        "domain_default": self.get_all_setting_domain_default(),
                        "list_rule_id": self.get_list_of_rule(),
                        "list_domain": self.get_list_of_domain()
                        }
        return all_settings
    
    def get_all_setting_system(self) -> None:
        """
        Return the system settingd
        """
        system = {
            "general": [
                {
                    "name":       "SOGO_S_MAILSPOOL_PATH",
                    "value":  "/var/spool/mail",
                },
            ]
        }
        return system

    def get_all_setting_domain_default(self) -> None:
        """
        Retrun the default settings for all domains
        """
        domain_default = {
            "Basic": [
                {
                    "name": "SOGO_D_AUTH_TYPE",
                    "value": "plain"
                }
            ],
            "User Source": [
                {
                    "name":  "US_TYPE",
                    "value": "sql"
                },
                {
                    "name":    "LDAP_GROUP_CLASS",
                    "value":  ['group', 'groupOfNames', 'sogo_group'],
                }
            ],
            "Advanced": [
                {
                    "name":   "SOGO_D_IDENTITIES_ENABLED",
                    "value":  False,
                },
                {
                    "name":   "SOGO_D_FOLDER_DISABLE_SHARING",
                    "value":  True,
                }
            ]
        }
        return domain_default

    def get_list_of_rule(self) -> None:
        """
        Return all the rules ids
        """
        return [{"id": 1,"name": "suisse"}, {"id": 2,"name": "Université"}]

    def get_list_of_domain(self) -> None:
        """
        Return all the domains
        """
        return  ["example.org", "sogo.nu", "business.com"]

    def get_all_setting_rule(self, rule_id: int) -> None:
        """
        Return settings for a specific rule
        """
        rule_default = {
            1: {
                "list_domains": ["sogo.nu", "business.com"],
                "description": "Those domains can create identities as per contract A38",
                "Advanced": [
                    {
                        "name":   "SOGO_D_IDENTITIES_ENABLED",
                        "value":  True,
                    }
                ]
            },
            2: {
                "list_domains": ["example.org", "business.com"],
                "description": "Those domains are configured on a ldap user source",
                "User Source": [
                {
                    "name":  "US_TYPE",
                    "value": "ldap"
                }]
            },
        }
        if rule_id in rule_default:
            return rule_default[rule_id]

        return None

    
    def get_all_setting_domain(self, domain_id: str) -> None:
        """
        Return settings for a specific domain
        """
        domain_setting = {
            "sogo.nu": {
                "Basic": [
                    {
                        "name": "SOGO_D_AUTH_TYPE",
                        "value": "plain",
                        "origin": {"type": "default"}
                    }],
                "User Source": [
                    {
                        "name":  "US_TYPE",
                        "value": "sql",
                        "origin": {"type": "default"},
                    },
                    {
                        "name":    "LDAP_GROUP_CLASS",
                        "value":  ['group', 'groupOfNames', 'sogo_group'],
                    }],
                "Advanced": [
                    {
                        "name":   "SOGO_D_IDENTITIES_ENABLED",
                        "value":  True,
                        "origin": {"type": "rule", "id": 1, "name": "suisse"}
                    },
                    {
                        "name":   "SOGO_D_FOLDER_DISABLE_SHARING",
                        "value":  False,
                        "origin": {"type": "domain"}
                    }
                ]
            },
            "example.org": {
                "Basic": [
                    {
                        "name": "SOGO_D_AUTH_TYPE",
                        "value": "plain",
                        "origin": {"type": "default"},
                    }
                ],
                "User Source": [
                    {
                        "name":  "US_TYPE",
                        "value": "ldap",
                        "origin": {"type": "rule", "id": 2, "name": "Université"}
                    },
                    {
                        "name":    "LDAP_GROUP_CLASS",
                        "value":  ['group', 'groupOfNames', 'sogo_group'],
                        "origin": {"type": "default"},
                    }
                ],
                "Advanced": [
                    {
                        "name":   "SOGO_D_IDENTITIES_ENABLED",
                        "value":  False,
                        "origin": {"type": "default"},
                    },
                    {
                        "name":   "SOGO_D_FOLDER_DISABLE_SHARING",
                        "value":  True,
                    }
                ]
            },
            "business.com": {
                "Basic": [
                    {
                        "name": "SOGO_D_AUTH_TYPE",
                        "value": "plain",
                        "origin": {"type": "default"},
                    }
                ],
                "User Source": [
                    {
                        "name":  "US_TYPE",
                        "value": "ldap",
                        "origin": {"type": "rule", "id": 2, "name": "Université"}
                    },
                    {
                        "name":    "LDAP_GROUP_CLASS",
                        "value":  ['group', 'groupOfNames', 'sogo_group'],
                        "origin": {"type": "default"},
                    }
                ],
                "Advanced": [
                    {
                        "name":   "SOGO_D_IDENTITIES_ENABLED",
                        "value":  True,
                        "origin": {"type": "rule", "id": 1, "name": "suisse"},
                    },
                    {
                        "name":   "SOGO_D_FOLDER_DISABLE_SHARING",
                        "value":  True,
                        "origin": {"type": "default"},
                    }
                ]
            },
        }
    
        if domain_id in domain_setting:
            return domain_setting[domain_id]
        return None
