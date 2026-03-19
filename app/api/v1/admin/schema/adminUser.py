from marshmallow import Schema, fields

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class AdminUserActiveSchema(ApiBaseResponse):
    """
    Schema for GET /users/active response.
    Returns the list of currently active users with their last activity timestamp.
    """
    data = fields.List(fields.Dict(), required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example response for active users list.

        :return: Example active users response
        :rtype: dict
        """
        return {
            "error_code": "S000000",
            "error_msg": "No Error",
            "data": [
                {
                    "uid": "jdoe@example.org",
                    "last_activity": "2026-03-06T10:42:00+00:00"
                },
                {
                    "uid": "jsmith@example.org",
                    "last_activity": "2026-03-06T11:00:00+00:00"
                }
            ]
        }


class AdminUserRevokeSchema(ApiBaseResponse):
    """
    Schema for POST /users/revoke response.
    Returns the number of sessions that were revoked.
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example response for a revoke call.

        :return: Example revoke response
        :rtype: dict
        """
        return {
            "error_code": "S000000",
            "error_msg": "No Error",
            "data": {
                "revoked": 2
            }
        }


class AdminUserRevokeBodySchema(Schema):
    """
    Schema for POST /users/revoke request body.
    """
    uid = fields.List(fields.String(), required=True, metadata={"description": "List of UIDs to revoke"})

    @classmethod
    def example(cls) -> dict:
        """
        Example request body for a revoke call.

        :return: Example revoke request body
        :rtype: dict
        """
        return {
            "uid": [
                "jdoe@example.org",
                "jsmith@example.org"
            ]
        }
