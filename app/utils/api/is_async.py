"""
Decorator and schema to add an optional 'is_async' query parameter to Flask API endpoints.
"""
from functools import wraps
from typing import Callable, Any
from marshmallow import Schema, fields
from flask import g


class AsyncQueryArgsSchema(Schema):
    """Schema for optional 'is_async' query parameter."""
    is_async = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            "description": "Whether to perform the action asynchronously. Defaults to false.",
        }
    )


def async_endpoint(func: Callable) -> Callable:
    """
    Decorator to add an optional 'is_async' boolean query parameter to a Flask endpoint method.
    
    The 'is_async' parameter is optional and must be either 'true' or 'false'.
    The parsed boolean value is stored in g.is_async for use within the endpoint.
    
    This decorator should be applied to individual HTTP method handlers (get, post, etc.),
    and should be combined with @blp.arguments(AsyncQueryArgsSchema, location='query')
    for proper Swagger documentation.
    
    Example:
        @blp.route('/api/example')
        class MyEndpoint(MethodView):
            @async_endpoint
            @blp.response(...)
            @blp.arguments(AsyncQueryArgsSchema, location='query')
            def post(self, query_args):
                if g.is_async:
                    # Handle async execution
                else:
                    # Handle sync execution
                return response
    
    :param func: The Flask view method function to decorate
    :return: The wrapped function
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Extract is_async from arguments
        # When used with @blp.arguments, query_args is the second positional argument (after self)
        query_args = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
        is_async_value = query_args.get('is_async', False)

        # Store in g for use within the endpoint
        g.is_async = bool(is_async_value)

        # Call the original function
        return func(*args, **kwargs)

    return wrapper
