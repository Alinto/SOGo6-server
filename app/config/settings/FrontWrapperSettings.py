"""
To avoid harcoding settings in the front server, SOGo use a specific syntax to send the
settings that allowed the front server to dynamically create them.

each settings is converting to a dictionnary with:

* name: Name of the settings, is used to find the translated label.
(* description): the translated description is found with '{name}_DSCR'
* data_type: type of the input
* default: default value
* required: settings can be empty
* subparent: if needed, name of the subparent
* constraints: constraint on the input (min value, length,... )
* depends: This input is only show if another value is set to something.
           Format is <another_input_name>%%%<equals,greater,lesser>%%%<value>
           The '%%%' is the delimiter.
"""

from marshmallow import Schema, fields, validate

from app.utils.logger.logger import logger

def fetch_inner_data_type(list_field: fields.List) -> str:
    """
    Fetch the inner field of a list and return the correct value
    """
    _inner_field = list_field.inner
    data_type = DATA_TYPE.get(type(_inner_field), None)
    if data_type is None:
        logger.error("fields.List '%s' inner field was not found: %s", list_field.name, type(_inner_field))
    elif data_type != "list":
        data_type = f"list[{data_type}]"
    else:
        data_type = f"list[{fetch_inner_data_type(_inner_field)}]"
    return data_type


DATA_TYPE = {
    fields.Boolean: "checkbox",
    fields.Integer: "number",
    fields.List:    "list",
    fields.Email:   "email",
    fields.String:  "text",
    fields.Url:     "url"
}

PARENT = {
    "system", "domain", "user"
}

example = {
    "system": {
         "general": [
            {
                "name":       "SOGO_S_MAILSPOOL_PATH",
                "data_type":  "str",
                "default":    "/var/spool/sogo",
                "required":   True,
                "subparent": "User Source",
                "constrains": None,
                "depends":    None
            },
         ]
    },
    "domain": {
        "Basic": [
            {
                "name":       "SOGO_D_AUTH_TYPE",
                "data_type":  "str",
                "default":    ['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup'],
                "required":   True,
                "subparent": "Basic",
                "constrains": {"choices": ['plain', 'openid', 'cas', 'saml2']},
                "depends":    None,
            }
        ],
        "User Source": [
            {
                "name":       "US_TYPE",
                "data_type":  "str",
                "default":    None,
                "required":   True,
                "subparent": "User Source",
                "constrains": {"choices": ["ldap", "sql"]},
                "depends":    None,
            },
            {
                "name":       "LDAP_GROUP_CLASS",
                "data_type":  "list[str]",
                "default":    ['group', 'groupOfNames', 'groupOfUniqueNames', 'posixGroup'],
                "required":   True,
                "subparent": "User Source",
                "constrains": None,
                "depends":    r"US_TYPE%%%equal%%%ldap",
            }
        ],
        "Advanced": [
            {
                "name":       "SOGO_D_IDENTITIES_ENABLED",
                "data_type":  "bool",
                "default":    False,
                "required":   True,
                "subparent": "Advanced",
                "constrains": None,
                "depends":    None
            },
            {
                "name":       "SOGO_D_FOLDER_DISABLE_SHARING",
                "data_type":  "bool",
                "default":    False,
                "required":   False,
                "subparent": "Advanced",
                "constrains": None,
                "depends":    None
            }
        ]
    }
}
