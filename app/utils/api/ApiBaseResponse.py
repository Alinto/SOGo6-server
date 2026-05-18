from typing import Any

from marshmallow import Schema, fields

from app.utils.errors import E, ERROR_NO_ERROR

class ApiBaseResponse(Schema):
    """
    Basic response for api
    """
    data : fields.Field = fields.Field(required=True, allow_none=True)
    error_msg = fields.String(required=True)
    error_code = fields.String(required=True)

#def create_api_base_response(data: Any|None = None, error: E = ERROR_NO_ERROR, code: int = 0) -> tuple[dict, int]:

def create_api_base_response(data: Any|None = None, error: E = ERROR_NO_ERROR, code: int = 0, error_msg: str | None = None) -> tuple[dict, int]:
    #ajouter un argument de code erreur ou si il est présent on met celui là, sinon on met celui de l'exception
    """
    Create the common API response.

    {
        "data": data,
        "error_code": error_code,
        "error_msg": error_msg
    }

    :param data: actual response for the endpoint
    :type data: dict
    :param error_code: code of the error, defaults to 0
    :type error_code: int, optional
    :raises BugException: wrong error_code given
    :return: the common response
    :rtype: dict
    """
    status = code if code else error.h
    return {
        "data": data,
        "error_code": error.c,
        "error_msg": error_msg if error_msg is not None else error.m
    }, status
