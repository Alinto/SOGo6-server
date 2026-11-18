from marshmallow import Schema, fields, validate


class UserMfaBeginSchema(Schema):
    """
    Body of POST /mfa: start the setup of a method
    """
    #Required only if several methods are allowed for the domain
    provider = fields.String(validate=validate.Length(min=1, max=64))
    #Code of the current method, required only to replace an existing method
    code = fields.String(validate=validate.Length(min=1, max=64))

    @classmethod
    def example(cls) -> dict:
        """
        Example for POST /mfa
        """
        return {"provider": "totp"}


class UserMfaCodeSchema(Schema):
    """
    Body with a code: POST /mfa/confirm and DELETE /mfa
    """
    code = fields.String(required=True, validate=validate.Length(min=1, max=64))

    @classmethod
    def example(cls) -> dict:
        """
        Example of body with a code
        """
        return {"code": "123456"}
