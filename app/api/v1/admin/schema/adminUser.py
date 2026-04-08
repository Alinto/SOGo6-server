from marshmallow import Schema, fields, validates_schema, ValidationError

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class AdminUserActiveSchema(ApiBaseResponse):
    """
    Schema for GET /users/active response.
    Returns the list of currently active users with their last activity timestamp.
    """
    data = fields.List(fields.Dict(), required=False, allow_none=True)

    @staticmethod
    def sort_by_values() -> set:
        """
        return values available for sorting by
        """
        return {"uid", "domain", "last_activity"}

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
                    "domain": "example.org",
                    "last_activity": "1775049291",
                    "session_key": "user_session:abc123"
                },
                {
                    "uid": "jsmith@example.org",
                    "domain": "example.org",
                    "last_activity": "1775049289",
                    "session_key": "user_session:def456"
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
    Exactly one of ``uid`` or ``redis_key`` must be provided.
    """
    uid = fields.List(fields.String(), load_default=None, metadata={"description": "List of UIDs to revoke"})
    redis_key = fields.List(fields.String(), load_default=None, metadata={"description": "List of Redis keys to revoke"})

    @validates_schema
    def validate_exclusive_fields(self, data: dict, **kwargs: object) -> None:
        """
        Ensure exactly one of ``uid`` or ``redis_key`` is provided.
        """
        has_uid = data.get("uid") is not None
        has_key = data.get("redis_key") is not None
        if has_uid == has_key:
            raise ValidationError("Exactly one of 'uid' or 'redis_key' must be provided.")

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
