from marshmallow import Schema, fields

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class AuthUserGetMechSchema(Schema):
    """
    Data schema of the result for /dynamic-form
    """
    username = fields.String(required=True)
    redirect = fields.String(load_default="", dump_default="")

class AuthUserBasicPostSchema(Schema):
    """
    Data schema of the result for /dynamic-form
    """
    username = fields.String(required=True)
    password = fields.String(required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example for the POST login

        :return: _description_
        :rtype: dict
        """
        return {
            "username": "sogo-tests1@example.org",
            "password": "sogo"
        }

