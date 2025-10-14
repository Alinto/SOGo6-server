"""
To avoid harcoding settings in the front server, SOGo use a specific syntax to send the
settings that allowed the front server to dynamically create them.

each settings is converting to a dictionnary with:

* name: Name of the settings, is used to find the translated label.
* data_type: type of the input
* default: default value
* required: settings can be empty
* constraints: constraint on the input (min value, length,... )
* depends: This input is only show if another value is set to something.
           Format is <another_input_name>%%%<equals,greater,lesser>%%%<value>
           The '%%%' is the delimiter.

constraints:
choices: a list a possible value for this parameter (ex: ['ldap', 'sql'])
min or min_inclusive: number, minimun value for this parameter (ex: 0)
max or max_inclusive: number, maximun value for this parameter (ex: 10)
prefix: fixed prefix for this parameters (ex: 'maitlo:')
prefixes: list of fixed choices of prefix for this parameter (ex ['http://', 'https://'])
len_min: number, minimum lenght of this string (ex: 4)
len_max: number, maximum lenght of this string (ex: 12)

"""


from typing import Any, Callable
from marshmallow import fields, validate
from marshmallow.constants import _Missing

from app.config.settings.SogoSchema import SogoSchema
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
        data_type = f"list[{fetch_inner_data_type(_inner_field)}]" #type: ignore
    return data_type


DATA_TYPE = {
    fields.Boolean: "bool",
    fields.Integer: "number",
    fields.List:    "list",
    fields.Email:   "email",
    fields.String:  "str",
    fields.Url:     "url",
    fields.Dict:    "dict",
    fields.Float:   "float"
}

def validate_one_of_to_constraint(my_validate: validate.OneOf) -> dict:
    """
    Convert a Validator OneOf to a dict for the dynamic form

    :param my_validate: The validator OneOf to convert
    :type my_validate: validate.OneOf
    :return: the direct value for 'constraint"
    :rtype: dict
    """
    return {"choices": list(my_validate.choices)}

def validate_range_to_constraint(my_validate: validate.Range) -> dict:
    """
    Convert a Validator Range to a dict for the dynamic form

    :param my_validate: The validator Range to convert
    :type my_validate: validate.Range
    :return: the direct value for 'constraint"
    :rtype: dict
    """
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

def validate_url_to_constraint(my_validate: validate.URL) -> dict:
    """
    Convert a Validator URL to a dict for the dynamic form

    :param my_validate: The validator URL to convert
    :type my_validate: validate.URL
    :return: the direct value for 'constraint"
    :rtype: dict
    """
    schemes = my_validate.schemes
    new_schemes = [f"{sch}://" for sch in schemes]
    constraints: dict = {}
    if len(new_schemes) > 1:
        constraints = {"prefixes": new_schemes}
    else:
        constraints = {"prefix": new_schemes[0]}
    return constraints

def validate_contains_only_to_constraint(my_validate: validate.ContainsOnly) -> dict:
    """
    COnvert a Validator ContainsOnlut to a dict for the dynamic form

    :param my_validate: The validator COntainsOnly to convert
    :type my_validate: validate.ContainsOnly
    :return: the direct value for constraints
    :rtype: dict
    """
    choices = list(my_validate.choices)
    constraints = {
        "choices": choices,
        "len_min": 1,
        "len_max": len(choices)
    }
    return constraints


VALIDATE_TYPE: dict[Any, Callable] = {
    validate.OneOf: validate_one_of_to_constraint,
    validate.Range: validate_range_to_constraint,
    validate.URL: validate_url_to_constraint,
    validate.ContainsOnly: validate_contains_only_to_constraint
}

def create_dynamic_dict_for_settings(settings_schema: SogoSchema) -> dict:
    """
    Create and return the dynamic form for the UI.

    :param settings_schema: A marshmallow shewa will the parameters
    :type settings_schema: SogoSchema
    :raises BugException: _description_
    :raises BugException: _description_
    :raises BugException: _description_
    :return: The json ready dictionnary with the dynamic form structure
    :rtype: dict
    """
    subparent: str = settings_schema.subparent
    dependencies: dict = settings_schema.dependencies
    secrets: set = settings_schema.is_secret

    dynamic_form : dict = {}
    dynamic_field_list = []
    schema_fields = settings_schema.fields

    def _depend_formatter(var_name: str, value: str|bool) -> str:
        return f"{var_name}%%%equal%%%{value}"

    for field_name in schema_fields:
        field = schema_fields[field_name]

        #Get the data_type
        data_type: str|None = None
        if field_name in secrets:
            data_type = "secret"
        else:
            if isinstance(field, fields.List):
                data_type = fetch_inner_data_type(field)
            else:
                data_type = DATA_TYPE.get(type(field), None)

        #Get default value if any
        default = field.dump_default if not isinstance(field.dump_default, _Missing) else None

        #Get required value
        required = field.required

        #Get constraints value
        constraints: dict|None = None
        if field.validate:
            if type(field.validate) in VALIDATE_TYPE:
                constraints = VALIDATE_TYPE[type(field.validate)](field.validate)
        if isinstance(field, fields.Url):
            # for fields.Url, the url validator is always put in first position
            # Also there is always schemes by default so it can't be empty
            url_validator : validate.URL = field.validators[0] #type: ignore
            url_constraint = validate_url_to_constraint(url_validator)
            if constraints is None:
                constraints = url_constraint
            else:
                constraints.update(url_constraint)

        #Get depends value
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
