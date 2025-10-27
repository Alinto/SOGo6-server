from typing import Any
from marshmallow import Schema, validates_schema, ValidationError

class SogoSchema(Schema):
    """
    Marsmahllow schema used by Sogo for its settings.
    It only adds attributes used to create the dynamic form

    :param subparent: Name of the panel. ex: USER_SOURCE
    :type data: str

    :param dependencies: Use to indicate if a setting is only available if another setting equal a value
                         For example: {"setting2": ("setting1": True)}
                         Means that setting2 is only available if setting1 is True
    :type data: dict[str, tuple[str, Any]]

    :param is_required: If a setting has a dependency and is required, set it here as we can't put "required=True" in the field.
    :type data: set[str]

    :param is_secret: List the settings that are sceret or password. Indicates the UI to not show them.
    :type data: set[str]

    :param is_duplicable: Notify if this schema can have several blocks or is unique
    :type data: bool

    :param is_uid: If the schema is duplicable, set the key/pram which is unique accross all block
    :type data: str
    """
    subparent = ""
    dependencies: dict[str, tuple[str, Any]] = {}
    is_required: set[str] = set()
    is_secret: set = set()
    is_duplicable: bool = False
    is_uid: str = ""

    @validates_schema
    def validate_required_whith_dependency(self, data: dict, **kwargs: dict) -> None:
        """
        Some fields with dependency can't have the attribute 'required=True'
        as they will be expectedly missing in the data if the dependency is not satidfied.
        We check for them here. 

        :param data: data given to the schema
        :type data: dict
        :raises ValidationError: all the errors with the data
        """
        errors = {}
        for field in self.is_required:
            if field not in data:
                dependency, value = self.dependencies[field]
                if dependency in data and data[dependency] == value:
                    errors[field] = [f"Missing required field as {dependency}={value}"]
        if errors:
            raise ValidationError(errors)