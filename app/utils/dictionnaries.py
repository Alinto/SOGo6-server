# -*- coding: utf-8 -*-

"""
Defines utility for dict
"""

from collections import UserDict

from marshmallow import Schema, fields

class DictSettings(UserDict):
    """
    dict used for sogo settings
    {
    "Setting_Name" = {"field": marshmallow.fields(), "desc": "description"}
    }
    """
    def _check_key_value(self, key, value):
        """
        Check that key is a string and value a dict with the keys 'field'
        'default' and 'desc'. Also check that field is of a marshmallow field.

        :raise TypeError:
        :raise marshmallow.exceptions.ValidationError: 
        """
        if not isinstance(key, str):
            raise TypeError(f"DomainSettings key must be a string, found {type(key)} instead")
        if not isinstance(value, dict):
            raise TypeError(f"DomainSettings value must be a dict, found {type(value)} instead")
        if not {'field', 'desc'} <= set(value.keys()):
            raise TypeError(f"DomainSettings value must be a dict with keys set('field', 'default', 'desc')  found {value.keys()} instead")
        if not isinstance(value["field"], fields):
            raise TypeError(f"field value must be a marshmallow field, found {type(value["field"])} instead")

    def __init__(self, data : dict = None):
        self.fields   = dict()
        self.desc     = dict()
        if data:
            for key, value in data:
                self._check_key_value(key, value)
                self.fields[key]   = value["field"]
                self.desc[key]     = value["desc"]
        else:
            data = dict()
        super().__init__(data)

    def __setitem__(self, key, value):
        self._check_key_value(key,value)
        self.data[key]     = value
        self.fields[key]   = value["field"]
        self.desc[key]     = value["desc"]

    def get_schema(self) -> Schema:
        """
        Return a dict ready to generate a Marshmallow Schema
        """
        return Schema.from_dict(self.fields)()
