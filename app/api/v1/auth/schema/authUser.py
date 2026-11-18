from marshmallow import Schema, fields, validate

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


class AuthUserMfaCodeSchema(Schema):
    """
    Body with the code of the second factor
    """
    code = fields.String(required=True, validate=validate.Length(min=1, max=64))

    @classmethod
    def example(cls) -> dict:
        """
        Example for POST /auth/mfa/verify
        """
        return {"code": "123456"}
