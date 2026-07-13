
from json import dumps
from app.config.settings.DomainSettings import get_all_domain_schemas
from app.config.settings.DynamicFormSettings import create_values_dict_for_settings

my_dict: dict[str, dict] = {"settings": {}}

for schema in get_all_domain_schemas():
    my_dict["settings"].update(create_values_dict_for_settings(schema()))

print(dumps(my_dict, indent=4))
