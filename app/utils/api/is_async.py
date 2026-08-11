"""
Decorator and schema to add an optional 'is_async' query parameter to Flask API endpoints.
"""
from functools import wraps
from typing import Callable, Any
from marshmallow import Schema, fields
from flask import g, request


class AsyncQueryArgsSchema(Schema):
    """Schema for optional 'is_async' query parameter."""
    is_async = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            "description": "Whether to perform the action asynchronously. Defaults to true.",
        }
    )


def async_endpoint(func: Callable) -> Callable:
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
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Extract is_async directly from the query string
        # Defaults to True (async execution) if not specified
        is_async_value = request.args.get('is_async', 'true').lower()
        g.is_async = is_async_value in ('true', '1', 'yes')

        # Call the original function
        return func(*args, **kwargs)

    return wrapper
