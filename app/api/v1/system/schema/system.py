from marshmallow import fields

from app.utils.api.ApiBaseResponse import ApiBaseResponse

class SystemGetRetSchema(ApiBaseResponse):
    """
    Schema of the result GET /api/user/v1/preferences
    """
    data = fields.Dict(fields.String(), fields.Dict(fields.String(), fields.Raw()))

    @classmethod
    def example(cls) -> dict:
        """
        Example of result for GET /system

        :return: example
        :rtype: dict
        """
        return {
            "system": {
                "SOGO_S_DIRECT_LOGIN": True
                }
            }