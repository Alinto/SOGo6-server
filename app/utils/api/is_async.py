"""
Decorator and schema to add an optional 'is_async' query parameter to Flask API endpoints.
"""
from functools import wraps
from typing import Callable, Any


from flask import request
from flask_smorest import Blueprint
from marshmallow import Schema, fields
from webargs.flaskparser import FlaskParser

from app.utils.api.ApiBaseResponse import ApiBaseResponse

class AsyncQueryArgsSchema(Schema):
    """Schema for optional 'is_async' query parameter."""
    is_async = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            "description": "Whether to perform the action asynchronously. Defaults to False.",
        }
    )
    #TODO add a timeout parameter for is_async=False, emaning to call the main func using threading

class AsyncResultSchema(Schema):
    """Schema for async tasks"""
    job_id = fields.String(required=False, allow_none=True)

class ApiAsyncResultSchema(ApiBaseResponse):
    """Response schema for the import endpoint (handles both async and sync modes)."""

    data = fields.Nested(AsyncResultSchema, allow_none=True)

def async_endpoint(blp: Blueprint) -> Callable:
    """
    Decorator to add an optional 'is_async' boolean query parameter to a Flask endpoint method.
    
    The 'is_async' parameter is optional and defaults to True (async execution).
    The parsed boolean value is stored in g.is_async for use within the endpoint.
    
    This decorator should be applied to individual HTTP method handlers (get, post, etc.),
    and should be combined with @blp.arguments(AsyncQueryArgsSchema, location='query', arg_name='query_args')
    for proper Swagger documentation.
    
    :param func: The Flask view method function to decorate
    :return: The wrapped function
    """
    flask_parser = FlaskParser()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract is_async directly from the query string
            # Defaults to True (async execution) if not specified
            is_async_obj = flask_parser.parse(AsyncQueryArgsSchema, request, location="query")

            kwargs["is_async"] = is_async_obj["is_async"]

            # Call the original function
            return func(*args, **kwargs)

        wrapped = blp.arguments(AsyncQueryArgsSchema, location="query", arg_name="is_async")(wrapper)
        wrapped = blp.response(202, ApiAsyncResultSchema)(wrapped)
        return wrapped

    return decorator
