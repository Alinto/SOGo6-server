"""
Schema for admin authentication API
"""

from marshmallow import Schema, fields


class AdminAuthBasicPostSchema(Schema):
    """
    Data schema for admin login
    """
    username = fields.String(required=True)
    password = fields.String(required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for the POST admin login

        :return: Example data dict
        :rtype: dict
        """
        return {
            "username": "admin",
            "password": "admin"
        }
