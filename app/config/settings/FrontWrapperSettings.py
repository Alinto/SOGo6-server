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
from marshmallow.constants import _Missing

from app.utils.exceptions import BugException
from app.utils.logger.logger import logger

def fetch_inner_data_type(list_field: fields.List) -> str|None:
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
    fields.Url:     "url",
    fields.Dict:    "dict"
}

def validate_one_of_to_constraint(my_validate: validate.OneOf) -> dict:
    return {"choices": list(my_validate.choices)}

def validate_range_to_constraint(my_validate: validate.Range) -> dict:
    constraint = {}
    if my_validate.min is not None:
        if my_validate.min_inclusive:
            constraint["min_inclusive"] = my_validate.min
        else:
            constraint["min"] = my_validate.min
    if my_validate.max is not None:
        if my_validate.max_inclusive:
            constraint["max_inclusive"] = my_validate.max
        else:
            constraint["max"] = my_validate.max

    return constraint
    

VALIDATE_TYPE = {
    validate.OneOf: validate_one_of_to_constraint,
    validate.Range: validate_range_to_constraint
}

class SogoSchema(Schema):
    """
    Fake Schema for hint typing
    """
    subparent = ""
    dependencies: dict = {}


def create_dynamic_dict_for_settings(settings_schema: SogoSchema) -> dict:
    if not hasattr(settings_schema, "subparent"):
        logger.error("Mising subparent in schema %s", type(settings_schema))
        raise BugException(f"Mising subparent in schema {type(settings_schema)}")
    if not hasattr(settings_schema, "dependencies"):
        logger.error("Mising dependencies in schema %s", type(settings_schema))
        raise BugException(f"Mising dependencies in schema {type(settings_schema)}")
    subparent: str = settings_schema.subparent
    dependencies: dict = settings_schema.dependencies

    dynamic_form : dict = {}
    dynamic_field_list = []
    schema_fields = settings_schema.fields

    def _depend_formatter(var_name: str, value: str|bool) -> str:
        return f"{var_name}%%%equal%%%{value}"

    for field_name in schema_fields:
        field = schema_fields[field_name]
        if isinstance(field, fields.List):
            data_type = fetch_inner_data_type(field)
        else:
            data_type = DATA_TYPE.get(type(field), None)
        default = field.dump_default if not isinstance(field.dump_default, _Missing) else None
        required = field.required

        constraints = None
        if field.validate:
            if type(field.validate) in VALIDATE_TYPE:
                constraints = VALIDATE_TYPE[type(field.validate)](field.validate)
        if isinstance(field, fields.Url):
            url_validator : validate.URL = field.validators[0]
            schemes = url_validator.schemes
            new_schemes = [f"{sch}://" for sch in schemes]
            if constraints is None:
                if len(new_schemes) > 1:
                    constraints = {"prefixes": new_schemes}
                else:
                    constraints = {"prefix": new_schemes}

        if dependency := dependencies.get(field_name, None):
            depends = _depend_formatter(dependency[0], dependency[1])
        else:
            depends = None
        dynamic_field = {"name": field_name,
                        "data_type": data_type,
                        "default": default,
                        "required": required,
                        "constraints": constraints,
                        "depends": depends}
        dynamic_field_list.append(dynamic_field)
    dynamic_form[subparent] = dynamic_field_list

    return dynamic_form





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
                "default":    'plain',
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
