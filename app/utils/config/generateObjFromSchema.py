from marshmallow import fields
from marshmallow.constants import _Missing

from app.config.settings.SogoSchema import SogoSchema


TAB = "    "

FIELD_TYPING = {
    fields.Boolean: "bool",
    fields.Integer: "int",
    fields.List:    "list",
    fields.Email:   "str",
    fields.String:  "str",
    fields.Url:     "str",
    fields.Dict:    "dict",
    fields.Float:   "float"
}

FIELD_DEFAULT = {
    fields.Boolean: "False",
    fields.Integer: "0",
    fields.List:    "[]",
    fields.Email:   "\"\"",
    fields.String:  "\"\"",
    fields.Url:     "\"\"",
    fields.Dict:    r"{}",
    fields.Float:   "0.0"
}

def fetch_inner_data_type(list_field: fields.List) -> str:
    """
    Fetch the inner field of a list and return the correct value
    """
    _inner_field = list_field.inner
    if isinstance(_inner_field, fields.List):
        return f"list[{fetch_inner_data_type(_inner_field)}]"
    
    data_type = FIELD_TYPING.get(type(_inner_field), None)
    if data_type is None:
        return "list"
    return f"list[{data_type}]"

def typing_and_default_value_from_field(field: fields.Field) -> tuple[str,str]:
    """
    
    :param field: _description_
    :type field: fields
    """
    if isinstance(field, fields.List):
        field_type = fetch_inner_data_type(field)
    else:
        field_type = FIELD_TYPING[type(field)]

    return field_type, FIELD_DEFAULT[type(field)]



def print_settings_obj_from_schema(schema:SogoSchema) -> None:
    """
    Marshammlow schema are great to validate a dict but are not great to actually use the dict:

    ex:
    system_settings = {
        "param1": value1,
        "param2: value2
    }

    which means in the code we have to:

    system_settings["param1"] which is not conveniant

    Instead we would like to directly call the param like this:
    system_settings.param1
    -> easier to find
    -> autoformat
    -> typed

    For this we need another class, that matches the Schema param name and type.

    This method print such a class from a schema.
    """

    print(f"class {schema.__class__.__name__}Obj:")
    print(f'{TAB}"""\n{TAB}Obj with the fields of schema {schema.__class__.__name__} as attributes with the proper type.\n{TAB}"""\n')
    schema_fields = schema.fields
    for field_name, field in schema_fields.items():
        field = schema_fields[field_name]
        field_type, field_value = typing_and_default_value_from_field(field)

        default = field.dump_default if not isinstance(field.dump_default, _Missing) else field_value

        print(f"{TAB}{field_name}: {field_type} = {default}")

if __name__ == "__main__":
    from app.config.settings.SystemSettings import SystemSettings
    from app.config.settings.DomainSettings import get_all_domain_schemas

