# /workspace/app/utils/api/paginate_sort_filter.py
from functools import wraps
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from flask import make_response, jsonify
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate

from app.utils.api.pagin_sort_filter import FakePaginationParameters



class SortSchema(Schema):
    """Schema for sorting query parameters."""
    sort_by = fields.Str(load_default=None)
    sort_order = fields.Str(
        load_default="asc",
        validate=validate.OneOf(["asc", "desc"]),
    )


class FieldsFilterSchema(Schema):
    """Schema for filtering query parameters."""
    include_fields = fields.Str(
        load_default=None,
        data_key="fields",
        metadata={
            "description": "Comma separated list of fields (ex: fields=uid,subject)"
        },
    )


def custom_paginate(blp: Blueprint, pagination_schema: type[Schema] | None = None) -> Callable:
    """
    Add parameters to query for pagination with sorting, filtering

    :param blp: _description_
    :type blp: Blueprint
    :param pagination_schema: _description_, defaults to None
    :type pagination_schema: type[Schema] | None, optional
    :return: _description_
    :rtype: Callable
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            pagination_parameters = cast(FakePaginationParameters|None, kwargs.pop("pagination_parameters", None))
            if pagination_parameters:
                kwargs["first"] = pagination_parameters.first_item
                kwargs["last"] = pagination_parameters.last_item

            item_count, response, status_code = func(*args, **kwargs)

            if pagination_parameters:
                pagination_parameters.item_count = item_count

            # Si response est un dict, on le retourne avec le status_code
            return make_response(jsonify(response), status_code)

        wrapped = blp.arguments(FieldsFilterSchema, location="query", arg_name="fields_args")(wrapper)
        wrapped = blp.arguments(SortSchema, location="query", arg_name="sort_args")(wrapped)
        if pagination_schema:
            wrapped = blp.paginate(pagination_schema)(wrapped)
        else:
            wrapped = blp.paginate()(wrapped)
        return wrapped
    return decorator